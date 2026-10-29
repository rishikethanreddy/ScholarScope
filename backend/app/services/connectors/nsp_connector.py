"""Connector: NSP public scheme listing -> deadlines, opening dates, renewal windows, guideline links, new schemes."""
from __future__ import annotations

from sqlalchemy import select

from app.core.config import load_config_file
from app.models import ChangeEvent, Scholarship, ScholarshipSource, SourceDocument, utcnow
from app.services.connectors.base import ParserAnomaly, RunContext, previous_document, store_document, upsert_candidate
from app.services.connectors.nsp_listing import PARSER_VERSION, NspScheme, parse_nsp_listing
from app.services.matching import normalize_url, rank_matches
from app.services.normalize import normalize_name
from app.services.records import ObservationContext, add_evidence, commit_version, observe_field

METHOD = "nsp_listing_parser"
NSP_LISTING_PAGE = "scholarships.gov.in/all-scholarships"


def run(ctx: RunContext) -> None:
    db, src = ctx.db, ctx.source
    url = (src.target_urls or [src.base_url])[0]
    res = ctx.fetcher.fetch(url, src.allowed_url_patterns)
    for line in res.log:
        ctx.log(line)
    ctx.stats["pages_fetched"] += 1
    html = res.content.decode("utf-8", errors="replace")
    schemes = parse_nsp_listing(html, base_url=url if url.startswith("http") else "https://scholarships.gov.in/")

    prev = previous_document(db, src.id, url)
    doc = store_document(ctx, res, None, None)
    doc.text_excerpt = f"{PARSER_VERSION}: parsed {len(schemes)} schemes"
    if not schemes:
        raise ParserAnomaly("NSP listing parsed 0 schemes; page structure may have changed")
    if prev and prev.text_excerpt and ":" in prev.text_excerpt:
        try:
            prev_count = int(prev.text_excerpt.split("parsed ")[1].split()[0])
        except (IndexError, ValueError):
            prev_count = 0
        ratio = load_config_file("policies.json")["source_health"]["min_parsed_ratio_vs_previous"]
        if prev_count and len(schemes) < ratio * prev_count:
            raise ParserAnomaly(f"Parsed {len(schemes)} schemes vs {prev_count} previously; refusing partial update")
    ctx.log(f"{'fixture' if res.is_fixture else 'live page'} parsed: {len(schemes)} schemes ({PARSER_VERSION})")
    if prev and prev.content_sha256 == doc.content_sha256:
        ctx.stats["pages_unchanged"] += 1
        ctx.log("page bytes identical to previous successful fetch")
    else:
        ctx.content_changed = True

    published = list(db.scalars(select(Scholarship).where(Scholarship.is_published.is_(True))))
    links = {l.external_key: l for l in db.scalars(select(ScholarshipSource).where(ScholarshipSource.source_id == src.id))}
    seen_keys: set[str] = set()
    now = utcnow()

    for sch in schemes:
        ctx.stats["records_seen"] += 1
        key = normalize_name(sch.title)
        seen_keys.add(key)
        for w in sch.warnings:
            ctx.log(f"[{sch.title[:60]}] {w}")
        link = links.get(key)
        target = db.get(Scholarship, link.scholarship_id) if link else None
        if target is None:
            matches = rank_matches(sch.title, sch.guideline_url, sch.ministry, published)
            best = matches[0] if matches else None
            if best and best.decision == "auto":
                target = db.get(Scholarship, best.record_id)
                link = ScholarshipSource(scholarship_id=target.id, source_id=src.id, external_key=key,
                                         match_method="auto_similarity", match_score=best.score,
                                         currently_listed=True)
                db.add(link)
                links[key] = link
                ctx.log(f"matched '{sch.title[:60]}' -> {target.external_id} (score {best.score})")
            else:
                _new_candidate(ctx, sch, key, doc, [m.as_dict() for m in matches])
                continue
        ctx.stats["records_matched"] += 1
        link.last_seen_at = now
        if not link.currently_listed:
            link.currently_listed = True
            ctx.log(f"'{sch.title[:60]}' is listed again")
        _observe(ctx, target, sch, doc, now)

    # Schemes previously listed on this page but missing now.
    for key, link in links.items():
        if key in seen_keys or not link.currently_listed:
            continue
        link.currently_listed = False
        s = db.get(Scholarship, link.scholarship_id)
        db.add(ChangeEvent(
            scholarship_id=s.id, source_id=src.id, job_id=ctx.job.id, document_id=doc.id, field="listing_presence",
            change_kind="removed", old_value="listed", new_value="not listed", materiality="material",
            source_url=url, evidence_snippet="Scheme no longer appears on the NSP listing page.", method=METHOD,
            review_status="pending"))
        ctx.stats["changes_detected"] += 1
        ctx.touched_scholarships.add(s.id)
        ctx.log(f"'{s.name[:60]}' no longer listed; change queued for review")


def _observe(ctx: RunContext, s: Scholarship, sch: NspScheme, doc: SourceDocument, now) -> None:
    src = ctx.source
    snippet = (sch.snippet, sch.location)
    obs = ObservationContext(
        source_key=src.key, classification=src.classification, method=METHOD, source_id=src.id,
        source_url=doc.url, retrieved_at=now, document_id=doc.id, job_id=ctx.job.id,
        snippets={f: snippet for f in ("deadline", "open_date", "renewal_type", "official_source_url", "guideline_url")},
    )
    events = []
    if sch.deadline:
        events.append(observe_field(ctx.db, s, "deadline", sch.deadline, obs))
    if sch.open_date:
        events.append(observe_field(ctx.db, s, "open_date", sch.open_date, obs))
    if sch.renewal_only:
        events.append(observe_field(ctx.db, s, "renewal_type", "renewal", obs))
    if sch.guideline_url:
        add_evidence(ctx.db, s, "guideline_url", sch.guideline_url, obs)
        # Replace a generic link to the listing page itself with the scheme-specific guideline.
        if not s.official_source_url or normalize_url(s.official_source_url) == NSP_LISTING_PAGE:
            events.append(observe_field(ctx.db, s, "official_source_url", sch.guideline_url, obs))
    events = [e for e in events if e is not None]
    s.last_checked_at = now
    if sch.deadline and s.deadline == sch.deadline:
        s.last_verified_at = now
    if events:
        ctx.stats["changes_detected"] += len(events)
        commit_version(ctx.db, s, f"Observed on {src.name}", None, events)
        for e in events:
            ctx.log(f"{s.external_id}: {e.field} {e.old_value} -> {e.new_value} [{e.review_status}]")
    ctx.touched_scholarships.add(s.id)


def _new_candidate(ctx: RunContext, sch: NspScheme, key: str, doc: SourceDocument, matches: list) -> None:
    payload = {
        "name": sch.title, "normalized_name": key, "provider": sch.ministry,
        "scholarship_type": (sch.scheme_type or "").lower().split()[0] if sch.scheme_type else None,
        "open_date": sch.open_date.isoformat() if sch.open_date else None,
        "deadline": sch.deadline.isoformat() if sch.deadline else None,
        "renewal_type": "renewal" if sch.renewal_only else "unknown",
        "official_source_url": sch.guideline_url, "application_url": "https://scholarships.gov.in/",
        "provider_type": "government",
    }
    ev = {f: {"snippet": sch.snippet, "location": sch.location}
          for f in ("name", "provider", "open_date", "deadline", "renewal_type", "official_source_url")}
    validation = {
        "errors": [],
        "warnings": ["Eligibility criteria are not on the listing page. Run extraction on the guideline document "
                     "or enter them manually before approval."] + sch.warnings,
        "unsupported": [],
        "missing_for_publication": ["education_levels", "income_rule", "academic_rule"],
    }
    if any(m["decision"] == "possible" for m in matches):
        validation["warnings"].insert(0, "Possible duplicate of an existing record; confirm before approving.")
    cand = upsert_candidate(ctx, external_key=key, title=sch.title, kind="new", payload=payload, evidence=ev,
                            validation=validation, possible_matches=matches, extraction_method=METHOD,
                            document_id=doc.id)
    if cand is not None:
        ctx.log(f"candidate: '{sch.title[:60]}' ({'possible match' if matches and matches[0]['decision'] == 'possible' else 'new'})")
