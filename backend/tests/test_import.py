from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import ChangeEvent, FieldEvidence, Scholarship, ScholarshipVersion
from app.services.ingestion.csv_import import ImportError_, import_dataset


def test_import_real_dataset(db, imported):
    assert imported.num_rows == 31 and imported.num_created == 31 and imported.num_rejected == 0
    assert db.scalar(select(func.count()).select_from(Scholarship)) == 31
    s = db.scalar(select(Scholarship).where(Scholarship.external_id == "IND-PRI-001"))
    assert s.min_percentage == 60 and s.min_cgpa is None  # legacy bug: 60% used to become CGPA 60
    assert s.deadline == date(2026, 10, 5)
    ev = db.scalar(select(FieldEvidence).where(FieldEvidence.scholarship_id == s.id, FieldEvidence.field == "deadline"))
    assert ev.verification_status == "dataset_claim" and "application_deadline=2026-10-05" in ev.snippet
    assert ev.retrieved_at.date() == date(2026, 9, 1)
    assert s.verification_status == "deadline_not_verified"  # dataset values are claims, not verified
    assert imported.report["rows_with_issues"] > 0


def test_reimport_identical_is_unchanged(db, imported, dataset_bytes):
    dv = import_dataset(db, dataset_bytes, file_name="dataset.csv", version="test-v2", dataset_name="test")
    assert dv.num_unchanged == 31 and dv.num_updated == 0
    assert db.scalar(select(func.count()).select_from(ChangeEvent)) == 0


def _modified(dataset_bytes: bytes) -> bytes:
    text = dataset_bytes.decode("utf-8")
    line = next(l for l in text.splitlines() if l.startswith('"IND-PRI-001",'))
    return text.replace(line, line.replace("2026-10-05", "2026-10-20")).encode("utf-8")


def test_reimport_review_mode_queues_changes(db, imported, dataset_bytes):
    import_dataset(db, _modified(dataset_bytes), file_name="d.csv", version="test-v2", dataset_name="test")
    s = db.scalar(select(Scholarship).where(Scholarship.external_id == "IND-PRI-001"))
    assert s.deadline == date(2026, 10, 5)  # not overwritten silently
    ev = db.scalar(select(ChangeEvent).where(ChangeEvent.field == "deadline"))
    assert ev.review_status == "pending" and ev.old_value == "2026-10-05" and ev.new_value == "2026-10-20"


def test_reimport_apply_mode_versions_and_keeps_history(db, imported, dataset_bytes):
    import_dataset(db, _modified(dataset_bytes), file_name="d.csv", version="test-v2", dataset_name="t", mode="apply")
    s = db.scalar(select(Scholarship).where(Scholarship.external_id == "IND-PRI-001"))
    assert s.deadline == date(2026, 10, 20) and s.version == 2
    versions = db.scalars(select(ScholarshipVersion).where(ScholarshipVersion.scholarship_id == s.id)
                          .order_by(ScholarshipVersion.version)).all()
    assert [v.snapshot["deadline"] for v in versions] == ["2026-10-05", "2026-10-20"]


def test_rejects_bad_files(db, imported):
    with pytest.raises(ImportError_, match="Missing required columns"):
        import_dataset(db, b"a,b\n1,2\n", file_name="x.csv", version="bad1", dataset_name="x")
    with pytest.raises(ImportError_, match="already exists"):
        import_dataset(db, b"x", file_name="x.csv", version="test-v1", dataset_name="x")
    with pytest.raises(ImportError_, match="UTF-8"):
        import_dataset(db, b"\xff\xfe\x00bad", file_name="x.csv", version="bad2", dataset_name="x")


def test_duplicate_and_missing_rows_rejected(db, dataset_bytes):
    import csv
    import io

    rows = list(csv.DictReader(io.StringIO(dataset_bytes.decode("utf-8"))))
    first = rows[0]
    nameless = {**first, "scholarship_id": "IND-NSP-999", "scholarship_name": ""}
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(first.keys()))
    w.writeheader()
    w.writerows([first, first, nameless])
    dv = import_dataset(db, out.getvalue().encode(), file_name="d.csv", version="dup", dataset_name="d")
    assert dv.num_created == 1 and dv.num_rejected == 2
    issues = [r["issues"] for r in dv.report["rows"] if r["status"] == "rejected"]
    assert any("duplicate scholarship_id" in " ".join(i) for i in issues)
    assert any("missing scholarship_name" in " ".join(i) for i in issues)
