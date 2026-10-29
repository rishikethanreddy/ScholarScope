"""Import a curated scholarship CSV (the researched dataset schema) into the catalogue.

* Normalizes every row (app/services/normalize.py) and records interpretation issues in an import report.
* New rows become published records with field evidence marked `dataset_claim` (not verified by this system).
* Re-imports never silently overwrite: differences become change events, either pending review (default)
  or accepted on behalf of the importing admin (mode="apply").
"""
from __future__ import annotations

import csv
import hashlib
import io
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DatasetVersion, Scholarship, utcnow
from app.services import trust
from app.services.normalize import clean, normalize_dataset_row, parse_date
from app.services.records import (
    CONTENT_FIELDS,
    EVIDENCED_FIELDS,
    ObservationContext,
    add_evidence,
    commit_version,
    observe_field,
)

REQUIRED_COLUMNS = {
    "scholarship_id", "scholarship_name", "provider", "education_level", "eligible_fields",
    "minimum_cgpa_or_percentage", "maximum_family_income", "gender", "category", "eligible_states",
    "application_start_date", "application_deadline", "official_source_url",
}

# Raw CSV columns that support each evidenced field (shown as the evidence snippet).
FIELD_COLUMNS = {
    "deadline": ["application_deadline"],
    "open_date": ["application_start_date"],
    "renewal_type": ["application_status"],
    "education_levels": ["education_level", "eligible_courses"],
    "disciplines": ["eligible_fields", "eligible_courses"],
    "academic_rule": ["minimum_cgpa_or_percentage", "minimum_marks_details"],
    "min_percentage": ["minimum_cgpa_or_percentage", "minimum_marks_details"],
    "min_cgpa": ["minimum_cgpa_or_percentage", "minimum_marks_details"],
    "income_rule": ["maximum_family_income", "income_criteria_details"],
    "income_limit": ["maximum_family_income", "income_criteria_details"],
    "genders": ["gender"],
    "categories": ["category"],
    "disability_rule": ["disability_requirement"],
    "eligible_states": ["eligible_states", "domicile_requirement"],
    "conditions": ["special_background_requirement"],
    "amount_text": ["scholarship_amount", "amount_frequency"],
    "required_documents": ["required_documents"],
    "application_url": ["official_application_url"],
    "official_source_url": ["official_source_url"],
}


class ImportError_(Exception):
    pass


def read_csv_bytes(data: bytes) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportError_("File is not valid UTF-8 text") from exc
    reader = csv.DictReader(io.StringIO(text))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise ImportError_(f"Missing required columns: {', '.join(sorted(missing))}")
    return list(reader)


def import_dataset(db: Session, data: bytes, *, file_name: str, version: str, dataset_name: str,
                   mode: str = "review", actor_id: Optional[str] = None) -> DatasetVersion:
    if mode not in ("review", "apply"):
        raise ImportError_("mode must be 'review' or 'apply'")
    if db.scalar(select(DatasetVersion).where(DatasetVersion.version == version)):
        raise ImportError_(f"Dataset version '{version}' already exists")
    rows = read_csv_bytes(data)
    if not rows:
        raise ImportError_("CSV contains no data rows")

    dv = DatasetVersion(
        dataset_name=dataset_name, version=version, file_name=Path(file_name).name,
        file_sha256=hashlib.sha256(data).hexdigest(), imported_by=actor_id, num_rows=len(rows),
    )
    db.add(dv)
    db.flush()

    row_reports, unknown_counter, seen_ids, seen_names = [], Counter(), set(), {}
    created = updated = unchanged = rejected = 0
    for i, row in enumerate(rows, start=2):  # header is line 1
        fields, issues = normalize_dataset_row(row)
        ext = fields["external_id"]
        if not ext:
            issues.append("REJECT: missing scholarship_id")
        elif ext in seen_ids:
            issues.append(f"REJECT: duplicate scholarship_id {ext} in file")
        if fields["normalized_name"] and fields["normalized_name"] in seen_names:
            issues.append(f"Possible duplicate of {seen_names[fields['normalized_name']]} (same normalized name)")
        for f in ("education_rule", "academic_rule", "income_rule", "discipline_rule"):
            if fields.get(f) == "unknown":
                unknown_counter[f] += 1
        if fields["deadline"] is None:
            unknown_counter["deadline"] += 1

        if any(x.startswith("REJECT") for x in issues):
            rejected += 1
            row_reports.append({"line": i, "external_id": ext, "status": "rejected", "issues": issues})
            continue
        seen_ids.add(ext)
        seen_names[fields["normalized_name"]] = ext

        verified = parse_date(row.get("source_last_verified"))
        ctx = ObservationContext(
            source_key=f"dataset:{version}", classification="curated_dataset", method="dataset_import",
            source_url=fields["official_source_url"],
            retrieved_at=datetime(verified.year, verified.month, verified.day, tzinfo=timezone.utc) if verified else None,
            verification_status="dataset_claim",
            snippets={
                f: ("; ".join(f"{c}={clean(row.get(c, ''))}" for c in cols), f"{file_name} line {i}")
                for f, cols in FIELD_COLUMNS.items()
            },
        )

        existing = db.scalar(select(Scholarship).where(Scholarship.external_id == ext))
        if existing is None:
            s = Scholarship(**fields, origin="dataset_import", dataset_version_id=dv.id, first_discovered_at=utcnow())
            db.add(s)
            db.flush()
            for f in EVIDENCED_FIELDS:
                add_evidence(db, s, f, fields.get(f), ctx)
            commit_version(db, s, f"Imported from dataset {version}", actor_id)
            created += 1
            status = "created"
        else:
            events = []
            for f in CONTENT_FIELDS:
                if f in EVIDENCED_FIELDS or getattr(existing, f) != fields.get(f):
                    ev = observe_field(db, existing, f, fields.get(f), ctx)
                    if ev:
                        if mode == "apply":
                            setattr(existing, f, fields.get(f))
                            ev.review_status = "accepted"
                            ev.reviewed_by = actor_id
                            ev.reviewed_at = utcnow()
                            ev.review_note = f"Accepted by dataset import {version} (mode=apply)"
                        events.append(ev)
            existing.dataset_version_id = dv.id
            if commit_version(db, existing, f"Re-import {version}", actor_id, events):
                updated += 1
                status = "updated"
            elif events:
                updated += 1
                status = "changes_pending"
            else:
                unchanged += 1
                status = "unchanged"
        row_reports.append({"line": i, "external_id": ext, "status": status, "issues": issues})

    dv.num_created, dv.num_updated, dv.num_unchanged, dv.num_rejected = created, updated, unchanged, rejected
    dv.report = {
        "rows": row_reports,
        "unknown_counts": dict(unknown_counter),
        "rows_with_issues": sum(1 for r in row_reports if r["issues"]),
        "mode": mode,
    }
    db.flush()
    trust.refresh_all(db)
    db.commit()
    return dv
