"""Crawl job lifecycle: enqueue (one active job per source), run, record outcome, update source health."""
from __future__ import annotations

import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import load_config_file
from app.database import SessionLocal
from app.models import CrawlJob, Scholarship, Source, utcnow
from app.services import trust
from app.services.connectors import nsp_connector, page_monitor
from app.services.connectors.base import ParserAnomaly, RunContext
from app.services.sources.fetcher import FetchError, SafeFetcher

log = logging.getLogger("scholarscope.crawl")

CONNECTORS: dict[str, Callable[[RunContext], None]] = {
    "nsp_listing": nsp_connector.run,
    "html_page": page_monitor.run,
    "pdf_document": page_monitor.run,
}

_source_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_executor: Optional[ThreadPoolExecutor] = None


class JobConflict(Exception):
    pass


def _lock_for(source_id: str) -> threading.Lock:
    with _locks_guard:
        return _source_locks.setdefault(source_id, threading.Lock())


def enqueue(db: Session, source: Source, trigger: str, requested_by: Optional[str] = None,
            retry_of: Optional[str] = None) -> CrawlJob:
    if source.connector not in CONNECTORS:
        raise ValueError(f"Unknown connector '{source.connector}'")
    active = db.scalar(select(CrawlJob).where(CrawlJob.source_id == source.id,
                                              CrawlJob.status.in_(("queued", "running"))))
    if active:
        raise JobConflict(f"A job for '{source.key}' is already {active.status} (job {active.id})")
    job = CrawlJob(source_id=source.id, trigger=trigger, requested_by=requested_by, retry_of=retry_of)
    db.add(job)
    db.commit()
    return job


def executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="crawl")
    return _executor


def submit(job_id: str) -> None:
    executor().submit(run_job, job_id)


def run_job(job_id: str, session_factory: sessionmaker = SessionLocal, fetcher: Optional[SafeFetcher] = None) -> str:
    db = session_factory()
    own_fetcher = fetcher is None
    fetcher = fetcher or SafeFetcher()
    try:
        job = db.get(CrawlJob, job_id)
        if job is None or job.status != "queued":
            return job.status if job else "missing"
        src = db.get(Source, job.source_id)
        lock = _lock_for(src.id)
        if not lock.acquire(blocking=False):
            job.status, job.error_type, job.finished_at = "skipped", "concurrent_job", utcnow()
            db.commit()
            return job.status
        try:
            return _execute(db, job, src, fetcher)
        finally:
            lock.release()
    finally:
        if own_fetcher:
            fetcher.close()
        db.close()


def _execute(db: Session, job: CrawlJob, src: Source, fetcher: SafeFetcher) -> str:
    entries: list[dict] = []

    def logline(msg: str) -> None:
        entries.append({"t": utcnow().isoformat(), "msg": msg[:1000]})
        log.info("[%s] %s", src.key, msg)

    job.status, job.started_at = "running", utcnow()
    src.last_attempt_at = job.started_at
    db.commit()
    ctx = RunContext(db=db, source=src, job=job, fetcher=fetcher, log=logline)
    policy = load_config_file("policies.json")["source_health"]
    try:
        CONNECTORS[src.connector](ctx)
        for sid in ctx.touched_scholarships:
            s = db.get(Scholarship, sid)
            if s:
                trust.refresh_status(db, s)
        now = utcnow()
        job.status = "succeeded"
        src.health_status, src.consecutive_failures, src.last_error = "healthy", 0, None
        src.last_success_at, src.last_http_status = now, 200
        if ctx.content_changed:
            src.last_change_at = now
        src.next_check_at = now + timedelta(minutes=_interval_minutes(src))
        src.paused_reason = None
    except (FetchError, ParserAnomaly, Exception) as exc:  # noqa: BLE001 - every failure must be recorded
        db.rollback()  # a failed check applies nothing: no partial updates, candidates or change events
        ctx.stats = {k: (v if k == "pages_fetched" else 0) for k, v in ctx.stats.items()}
        job = db.get(CrawlJob, job.id)
        src = db.get(Source, src.id)
        kind = exc.kind if isinstance(exc, FetchError) else ("parser_anomaly" if isinstance(exc, ParserAnomaly) else "internal_error")
        status = exc.status if isinstance(exc, FetchError) else None
        logline(f"FAILED ({kind}): {exc}")
        if kind == "internal_error":
            logline(traceback.format_exc(limit=3))
        job.status, job.error_type, job.error_message = "failed", kind, str(exc)[:2000]
        src.consecutive_failures += 1
        src.last_error = f"{kind}: {exc}"[:2000]
        src.last_http_status = status
        backoff_h = min(policy["max_backoff_hours"], (2 ** min(src.consecutive_failures, 10)) * _interval_minutes(src) / 60 / 4)
        if isinstance(exc, FetchError) and exc.retry_after:
            backoff_h = max(backoff_h, exc.retry_after / 3600)
        src.next_check_at = utcnow() + timedelta(hours=backoff_h)
        if kind == "access_denied" or (status in policy["pause_on_http_status"]):
            src.health_status = "paused"
            src.paused_reason = f"Access denied (HTTP {status}). Access controls are never bypassed; review the source."
        elif kind in ("robots_disallowed", "blocked_by_policy", "ssrf_blocked"):
            src.health_status = "paused"
            src.paused_reason = f"Blocked by crawl policy: {kind}"
        elif src.consecutive_failures >= policy["pause_after_consecutive_failures"]:
            src.health_status = "failing"
        else:
            src.health_status = "degraded"
        for link_sid in _linked_ids(db, src):
            s = db.get(Scholarship, link_sid)
            if s:
                trust.refresh_status(db, s)
    finally:
        job.finished_at = utcnow()
        for k, v in ctx.stats.items():
            setattr(job, k, v)
        job.log = entries
        db.commit()
    return job.status


def _linked_ids(db: Session, src: Source) -> list[str]:
    from app.models import ScholarshipSource

    ids = [l.scholarship_id for l in db.scalars(select(ScholarshipSource).where(ScholarshipSource.source_id == src.id))]
    if src.linked_scholarship_id:
        ids.append(src.linked_scholarship_id)
    return ids


def _interval_minutes(src: Source) -> int:
    """Crawl interval, shortened when the source changed recently (freshness policy)."""
    f = load_config_file("policies.json")["freshness"]
    base = max(5, src.crawl_frequency_minutes)
    if src.last_change_at:
        last = src.last_change_at if src.last_change_at.tzinfo else src.last_change_at.replace(tzinfo=utcnow().tzinfo)
        if utcnow() - last < timedelta(days=f["recently_changed_days"]):
            return max(5, int(base * f["recently_changed_crawl_factor"]))
    return base


def recover_interrupted_jobs(db: Session) -> int:
    """Jobs left queued/running by a previous process cannot still be running; mark them failed."""
    n = 0
    for job in db.scalars(select(CrawlJob).where(CrawlJob.status.in_(("queued", "running")))):
        job.status, job.error_type = "failed", "interrupted"
        job.error_message = "Process stopped before the job finished"
        job.finished_at = utcnow()
        n += 1
    db.commit()
    return n
