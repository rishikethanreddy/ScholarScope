"""In-process scheduler: every tick, enqueue a check for each enabled source that is due.

A single background thread is sufficient for this project's scale (a handful of sources, checked every few hours).
For multi-process deployments run exactly one scheduler (SCHEDULER_ENABLED=true on one instance only) or replace
this with a system cron calling `python -m app.cli crawl --due`.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from sqlalchemy import or_, select

from app.core.config import get_settings
from app.database import SessionLocal
from app.models import Source, utcnow
from app.services.crawl import orchestrator

log = logging.getLogger("scholarscope.scheduler")
_stop = threading.Event()
_thread: Optional[threading.Thread] = None
state = {"running": False, "last_tick_at": None, "last_enqueued": []}


def due_sources(db) -> list[Source]:
    now = utcnow()
    return list(db.scalars(select(Source).where(
        Source.enabled.is_(True), Source.health_status != "paused",
        or_(Source.next_check_at.is_(None), Source.next_check_at <= now))))


def tick() -> list[str]:
    enqueued = []
    db = SessionLocal()
    try:
        for src in due_sources(db):
            try:
                job = orchestrator.enqueue(db, src, "scheduled")
            except orchestrator.JobConflict:
                continue
            orchestrator.submit(job.id)
            enqueued.append(src.key)
    finally:
        db.close()
    state["last_tick_at"] = utcnow().isoformat()
    state["last_enqueued"] = enqueued
    if enqueued:
        log.info("scheduled checks: %s", ", ".join(enqueued))
    return enqueued


def _loop(interval: int) -> None:
    while not _stop.is_set():
        try:
            tick()
        except Exception:  # noqa: BLE001 - scheduler must survive individual failures
            log.exception("scheduler tick failed")
        _stop.wait(interval)


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(get_settings().scheduler_tick_seconds,), daemon=True,
                               name="scheduler")
    _thread.start()
    state["running"] = True


def stop() -> None:
    _stop.set()
    state["running"] = False
