from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Candidate, CrawlJob, Source, SourceDocument, utcnow
from app.services.extraction.text import ExtractedText
from app.services.sources.fetcher import FetchResult, SafeFetcher


class ParserAnomaly(Exception):
    """The page was fetched but did not have the expected structure; treated as a failed check, never as 'no data'."""


@dataclass
class RunContext:
    db: Session
    source: Source
    job: CrawlJob
    fetcher: SafeFetcher
    log: Callable[[str], None]
    stats: dict = field(default_factory=lambda: {
        "pages_fetched": 0, "pages_unchanged": 0, "records_seen": 0, "records_matched": 0,
        "candidates_created": 0, "changes_detected": 0})
    touched_scholarships: set = field(default_factory=set)
    content_changed: bool = False


def previous_document(db: Session, source_id: str, url: str) -> Optional[SourceDocument]:
    return db.scalar(
        select(SourceDocument)
        .where(SourceDocument.source_id == source_id, SourceDocument.url == url, SourceDocument.not_modified.is_(False))
        .order_by(SourceDocument.fetched_at.desc())
        .limit(1)
    )


def store_document(ctx: RunContext, res: FetchResult, extracted: Optional[ExtractedText], text_digest: Optional[str]
                   ) -> SourceDocument:
    storage_path = None
    digest = None
    if not res.not_modified:
        digest = hashlib.sha256(res.content).hexdigest()
        snap_dir = get_settings().snapshots_dir
        snap_dir.mkdir(parents=True, exist_ok=True)
        path = snap_dir / digest
        if not path.exists():
            path.write_bytes(res.content)
        storage_path = digest
    doc = SourceDocument(
        source_id=ctx.source.id, job_id=ctx.job.id, url=res.url, final_url=res.final_url, http_status=res.status,
        content_type=res.content_type[:120] if res.content_type else None, content_sha256=digest,
        text_sha256=text_digest, byte_size=len(res.content) if not res.not_modified else None,
        etag=res.etag, last_modified=res.last_modified, storage_path=storage_path,
        text_excerpt=extracted.text[:4000] if extracted else None,
        extraction_quality=extracted.quality if extracted else None, not_modified=res.not_modified,
        fetched_at=utcnow(),
    )
    ctx.db.add(doc)
    ctx.db.flush()
    return doc


def read_document_bytes(doc: SourceDocument) -> Optional[bytes]:
    if not doc.storage_path:
        return None
    path = get_settings().snapshots_dir / doc.storage_path
    return path.read_bytes() if path.exists() else None


def upsert_candidate(ctx: RunContext, *, external_key: str, title: str, kind: str, payload: dict, evidence: dict,
                     validation: dict, possible_matches: list, extraction_method: str, document_id: Optional[str],
                     matched_scholarship_id: Optional[str] = None) -> Optional[Candidate]:
    """Create a pending candidate, or refresh an existing pending one for the same source + key.

    Returns None (and logs) if the same item was previously rejected and its payload has not changed.
    """
    db = ctx.db
    existing = db.scalar(select(Candidate).where(
        Candidate.source_id == ctx.source.id, Candidate.external_key == external_key
    ).order_by(Candidate.created_at.desc()).limit(1))
    if existing and existing.status == "pending":
        # Merge: re-observed fields are refreshed, but values added later (AI extraction, reviewer context) are kept.
        existing.payload = {**(existing.payload or {}), **payload}
        existing.evidence = {**(existing.evidence or {}), **evidence}
        if existing.extraction_status != "succeeded":
            existing.validation = validation
        existing.possible_matches, existing.job_id = possible_matches, ctx.job.id
        return existing
    if existing and existing.status == "rejected" and existing.payload == payload:
        ctx.log(f"skipped previously rejected candidate '{title}'")
        return None
    if existing and existing.status == "approved" and kind == "new":
        return None
    cand = Candidate(
        kind=kind, source_id=ctx.source.id, job_id=ctx.job.id, document_id=document_id, external_key=external_key,
        title=title[:300], payload=payload, evidence=evidence, validation=validation,
        possible_matches=possible_matches, extraction_method=extraction_method,
        matched_scholarship_id=matched_scholarship_id,
        extraction_status={"llm": "succeeded", "llm_failed": "failed"}.get(extraction_method, "not_run"),
    )
    db.add(cand)
    ctx.stats["candidates_created"] += 1
    return cand
