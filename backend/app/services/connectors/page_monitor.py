"""Connector: monitor individual official HTML pages or PDF guidelines.

For each target URL: conditional fetch -> text extraction -> normalized-text hash comparison.
  * 304 / identical bytes        -> unchanged
  * bytes differ, text identical -> cosmetic change (logged, no review)
  * text differs                 -> material 'page_content' change queued for review, with a text diff;
                                    deadline statements found by deterministic rules are recorded as observations;
                                    optional LLM extraction produces an update candidate.
The first fetch of a URL only captures a baseline.
"""
from __future__ import annotations

import difflib

from app.models import ChangeEvent, Scholarship, utcnow
from app.services.connectors.base import (
    ParserAnomaly,
    RunContext,
    previous_document,
    read_document_bytes,
    store_document,
    upsert_candidate,
)
from app.services.extraction import extractor, llm
from app.services.extraction.text import extract, find_closure_statements, find_deadline_statements, text_hash
from app.services.normalize import parse_date
from app.services.records import ObservationContext, commit_version, observe_field

PARSER_VERSION = "page-monitor/1.0"


def text_diff(old: str, new: str, limit: int = 40) -> str:
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0))
    body = [l for l in lines if not l.startswith(("---", "+++", "@@"))]
    return "\n".join(body[:limit]) + ("\n…" if len(body) > limit else "")


def run(ctx: RunContext) -> None:
    db, src = ctx.db, ctx.source
    linked = db.get(Scholarship, src.linked_scholarship_id) if src.linked_scholarship_id else None
    now = utcnow()
    for url in src.target_urls or [src.base_url]:
        prev = previous_document(db, src.id, url)
        res = ctx.fetcher.fetch(url, src.allowed_url_patterns, etag=prev.etag if prev else None,
                                last_modified=prev.last_modified if prev else None)
        for line in res.log:
            ctx.log(line)
        ctx.stats["pages_fetched"] += 1
        if res.not_modified:
            store_document(ctx, res, None, prev.text_sha256 if prev else None)
            ctx.stats["pages_unchanged"] += 1
            ctx.log(f"{url}: 304 not modified")
            _mark_checked(ctx, linked, now)
            continue
        extracted = extract(res.content, res.content_type, url)
        if extracted.quality == "empty":
            store_document(ctx, res, extracted, None)
            raise ParserAnomaly(f"{url}: no readable text ({extracted.note})")
        digest = text_hash(extracted.text)
        doc = store_document(ctx, res, extracted, digest)
        if extracted.quality != "ok":
            ctx.log(f"{url}: extraction quality {extracted.quality}: {extracted.note}")

        if linked:
            _apply_rules(ctx, linked, extracted.text, doc, url, now)
        if prev is None:
            ctx.log(f"{url}: baseline captured ({len(extracted.text)} chars, {extracted.quality})")
            _mark_checked(ctx, linked, now)
            continue
        if prev.content_sha256 == doc.content_sha256:
            ctx.stats["pages_unchanged"] += 1
            ctx.log(f"{url}: unchanged")
            _mark_checked(ctx, linked, now)
            continue
        if prev.text_sha256 == digest:
            ctx.stats["pages_unchanged"] += 1
            db.add(ChangeEvent(
                scholarship_id=linked.id if linked else None, source_id=src.id, job_id=ctx.job.id,
                document_id=doc.id, field="page_content", change_kind="content", old_value=prev.content_sha256,
                new_value=doc.content_sha256, materiality="cosmetic", source_url=url,
                evidence_snippet="Raw bytes changed but the normalized main text is identical (layout/boilerplate).",
                method=PARSER_VERSION, review_status="informational"))
            ctx.log(f"{url}: cosmetic change only (main text identical)")
            _mark_checked(ctx, linked, now)
            continue

        # Material text change
        ctx.content_changed = True
        old_bytes = read_document_bytes(prev)
        old_text = extract(old_bytes, prev.content_type or "", url).text if old_bytes else (prev.text_excerpt or "")
        diff = text_diff(old_text, extracted.text)
        db.add(ChangeEvent(
            scholarship_id=linked.id if linked else None, source_id=src.id, job_id=ctx.job.id, document_id=doc.id,
            field="page_content", change_kind="content", old_value=prev.content_sha256, new_value=doc.content_sha256,
            materiality="material", source_url=url, evidence_snippet=diff[:4000], method=PARSER_VERSION,
            review_status="pending"))
        ctx.stats["changes_detected"] += 1
        ctx.log(f"{url}: main text changed; queued for review")

        if linked:
            _mark_checked(ctx, linked, now)
        if src.connector_config.get("auto_extract") and llm.status()["configured"]:
            _extract_candidate(ctx, linked, extracted.text, doc, url)


def _mark_checked(ctx: RunContext, s, now) -> None:
    if s is not None:
        s.last_checked_at = now
        ctx.touched_scholarships.add(s.id)


def _apply_rules(ctx: RunContext, s: Scholarship, text: str, doc, url: str, now) -> None:
    """Deterministic statements on the page, compared with the published record (not just the previous page)."""
    closures = find_closure_statements(text)
    if closures:
        obs = ObservationContext(source_key=ctx.source.key, classification=ctx.source.classification,
                                 method="html_rules", source_id=ctx.source.id, source_url=url, retrieved_at=now,
                                 document_id=doc.id, job_id=ctx.job.id, snippets={"status_reported": (closures[0], None)})
        ev = observe_field(ctx.db, s, "status_reported", "CLOSED (stated by source)", obs)
        if ev:
            ctx.stats["changes_detected"] += 1
            commit_version(ctx.db, s, f"Observed on {ctx.source.name}", None, [ev])
            ctx.log(f"closure statement found: '{closures[0][:120]}' ({ev.review_status})")
    _deadline_rules(ctx, s, text, doc, url, now)


def _deadline_rules(ctx: RunContext, s: Scholarship, text: str, doc, url: str, now) -> None:
    statements = find_deadline_statements(text)
    dates = {parse_date(d) for _, d in statements} - {None}
    if len(dates) != 1:
        if len(dates) > 1:
            ctx.log(f"{len(dates)} different deadline dates stated on page; not recorded (ambiguous)")
        return
    deadline = dates.pop()
    sentence = next(sn for sn, d in statements if parse_date(d) == deadline)
    obs = ObservationContext(source_key=ctx.source.key, classification=ctx.source.classification,
                             method="html_rules", source_id=ctx.source.id, source_url=url, retrieved_at=now,
                             document_id=doc.id, job_id=ctx.job.id, snippets={"deadline": (sentence, None)})
    ev = observe_field(ctx.db, s, "deadline", deadline, obs)
    if ev:
        ctx.stats["changes_detected"] += 1
        commit_version(ctx.db, s, f"Observed on {ctx.source.name}", None, [ev])
        ctx.log(f"deadline statement found: {deadline} ({ev.review_status})")
    elif s.deadline == deadline:
        s.last_verified_at = now


def _extract_candidate(ctx: RunContext, linked, text: str, doc, url: str) -> None:
    try:
        result = extractor.run_extraction(text, url)
    except llm.LLMError as err:
        ctx.log(f"LLM extraction failed ({err.kind}): {err}")
        upsert_candidate(ctx, external_key=url, title=(linked.name if linked else url), kind="update" if linked else "new",
                         payload={}, evidence={}, validation={"errors": [f"Extraction failed: {err}"], "warnings": [],
                                                              "unsupported": []},
                         possible_matches=[], extraction_method="llm_failed", document_id=doc.id,
                         matched_scholarship_id=linked.id if linked else None)
        return
    cand = upsert_candidate(
        ctx, external_key=url, title=result.payload.get("name") or (linked.name if linked else url),
        kind="update" if linked else "new", payload=result.payload, evidence=result.evidence,
        validation=result.validation, possible_matches=[], extraction_method="llm", document_id=doc.id,
        matched_scholarship_id=linked.id if linked else None)
    if cand:
        cand.llm_provider, cand.llm_model = result.provider, result.model
        ctx.log(f"LLM extraction produced candidate with {len(result.payload)} fields "
                f"({len(result.validation['unsupported'])} unsupported values rejected)")
