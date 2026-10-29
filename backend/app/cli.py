"""Command line operations.

  python -m app.cli init                         apply migrations, seed sources, import the bundled dataset
  python -m app.cli migrate                      apply database migrations (alembic upgrade head)
  python -m app.cli seed-sources                 load config/sources.json (existing keys untouched)
  python -m app.cli create-admin --email E       create/promote an admin (password from ADMIN_PASSWORD or prompt)
  python -m app.cli import --file F --version V [--name N] [--mode review|apply]
  python -m app.cli crawl --source KEY | --due | --all
  python -m app.cli refresh-trust
  python -m app.cli demo-setup                   build the offline demo database (fixture sources, clearly labelled)
  python -m app.cli demo-revision [--n 1|2]      swap the demo NSP fixture to the synthetic revision (2) or back (1)
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import BACKEND_DIR, get_settings, load_config_file
from app.database import SessionLocal

DEFAULT_DATASET = BACKEND_DIR / "data" / "imports" / "india_scholarship_dataset_2026_27_researched.csv"


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")
    print("database migrated")


def seed_sources(path: Path | None = None) -> int:
    from app.models import Scholarship, ScholarshipSource, Source

    data = json.loads((path or BACKEND_DIR / "config" / "sources.json").read_text(encoding="utf-8"))
    n = 0
    with SessionLocal() as db:
        for raw in data["sources"]:
            if db.scalar(select(Source).where(Source.key == raw["key"])):
                continue
            raw = dict(raw)
            ext = raw.pop("linked_external_id", None)
            src = Source(**raw)
            if ext:
                s = db.scalar(select(Scholarship).where(Scholarship.external_id == ext))
                src.linked_scholarship_id = s.id if s else None
            db.add(src)
            db.flush()
            if src.linked_scholarship_id:
                db.add(ScholarshipSource(scholarship_id=src.linked_scholarship_id, source_id=src.id,
                                         external_key=src.target_urls[0], match_method="configured"))
            n += 1
        db.commit()
    print(f"seeded {n} sources")
    return n


def create_admin(email: str) -> None:
    from app.core.security import hash_password
    from app.models import User

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password (min 10 chars): ")
    if len(password) < 10:
        sys.exit("password must be at least 10 characters")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user:
            user.role, user.password_hash = "admin", hash_password(password)
        else:
            db.add(User(email=email.lower(), password_hash=hash_password(password), role="admin"))
        db.commit()
    print(f"admin ready: {email}")


def import_file(file: Path, version: str, name: str, mode: str) -> None:
    from app.services.ingestion.csv_import import import_dataset

    with SessionLocal() as db:
        dv = import_dataset(db, file.read_bytes(), file_name=file.name, version=version, dataset_name=name, mode=mode)
        print(f"imported {dv.version}: {dv.num_rows} rows, {dv.num_created} created, {dv.num_updated} updated, "
              f"{dv.num_unchanged} unchanged, {dv.num_rejected} rejected, "
              f"{dv.report['rows_with_issues']} rows with interpretation notes")


def crawl(source_key: str | None, due: bool, all_: bool) -> int:
    from app.models import Source
    from app.services.crawl import orchestrator, scheduler

    with SessionLocal() as db:
        if source_key:
            sources = [db.scalar(select(Source).where(Source.key == source_key))]
            if sources[0] is None:
                sys.exit(f"unknown source {source_key}")
        elif due:
            sources = scheduler.due_sources(db)
        else:
            sources = list(db.scalars(select(Source).where(Source.enabled.is_(True))))
        jobs = []
        for src in sources:
            try:
                jobs.append((src.key, orchestrator.enqueue(db, src, "cli").id))
            except orchestrator.JobConflict as exc:
                print(f"skip {src.key}: {exc}")
    failures = 0
    for key, job_id in jobs:
        status = orchestrator.run_job(job_id)
        with SessionLocal() as db:
            from app.models import CrawlJob

            j = db.get(CrawlJob, job_id)
            print(f"{key}: {status} | seen={j.records_seen} matched={j.records_matched} changes={j.changes_detected} "
                  f"candidates={j.candidates_created} {('| ' + j.error_type + ': ' + (j.error_message or '')[:150]) if j.error_type else ''}")
        failures += status != "succeeded"
    return failures


def refresh_trust() -> None:
    from app.services import trust

    with SessionLocal() as db:
        n = trust.refresh_all(db)
        db.commit()
    print(f"refreshed {n} records")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("migrate")
    sub.add_parser("seed-sources")
    a = sub.add_parser("create-admin")
    a.add_argument("--email", required=True)
    i = sub.add_parser("import")
    i.add_argument("--file", type=Path, default=DEFAULT_DATASET)
    i.add_argument("--version", required=True)
    i.add_argument("--name", default="Researched India scholarship dataset 2026-27")
    i.add_argument("--mode", choices=["review", "apply"], default="review")
    c = sub.add_parser("crawl")
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--source")
    g.add_argument("--due", action="store_true")
    g.add_argument("--all", action="store_true")
    sub.add_parser("refresh-trust")
    sub.add_parser("demo-setup")
    dr = sub.add_parser("demo-revision")
    dr.add_argument("--n", type=int, choices=[1, 2], default=2)
    args = p.parse_args(argv)

    if args.cmd == "init":
        migrate()
        from app.models import DatasetVersion

        with SessionLocal() as db:
            has_data = db.scalar(select(DatasetVersion.id).limit(1)) is not None
        if not has_data:
            import_file(DEFAULT_DATASET, "2026-27-researched-v1", "Researched India scholarship dataset 2026-27", "review")
        seed_sources()
    elif args.cmd == "migrate":
        migrate()
    elif args.cmd == "seed-sources":
        seed_sources()
    elif args.cmd == "create-admin":
        create_admin(args.email)
    elif args.cmd == "import":
        import_file(args.file, args.version, args.name, args.mode)
    elif args.cmd == "crawl":
        sys.exit(1 if crawl(args.source, args.due, args.all) else 0)
    elif args.cmd == "refresh-trust":
        refresh_trust()
    elif args.cmd == "demo-setup":
        from app import demo

        demo.setup()
    elif args.cmd == "demo-revision":
        from app import demo

        demo.use_revision(args.n)


if __name__ == "__main__":
    main()
