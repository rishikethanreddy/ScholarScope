# Database

Defined in `backend/app/models.py`; migrations in `backend/migrations/` (Alembic, initial revision `fb77eed08894`).

## Tables

| Group | Table | Purpose |
|---|---|---|
| Identity | `users` | email, scrypt password hash, role (`student`/`admin`) |
| | `student_profiles` | only attributes an eligibility rule uses; all optional (null = unknown) |
| | `student_answers` | yes/no/unsure answers to scholarship-specific conditions |
| | `saved_scholarships` | bookmarks and application tracking status |
| | `recommendation_snapshots` | compact result snapshot used for "what changed for me" |
| Catalogue | `scholarships` | current published record (structured rules + freshness summary) |
| | `scholarship_versions` | full JSON snapshot per version; never overwritten |
| | `field_evidence` | one observation of one field from one source (value, snippet, location, method, time, status, `is_current`) |
| | `scholarship_sources` | many-to-many link: which sources describe which record, `currently_listed` |
| | `dataset_versions` | each CSV import with SHA-256 and a per-row interpretation report |
| Monitoring | `sources` | registry: classification, URLs, allowlist, connector, frequency, health, backoff |
| | `crawl_jobs` | every check: trigger, status, counts, error type/message, log |
| | `source_documents` | each retrieval: URL, HTTP status, hashes (bytes and normalized text), ETag/Last-Modified, storage path |
| Review | `change_events` | old/new value, materiality, method, evidence, review status, applied version |
| | `candidates` | proposed new/updated records with payload, evidence, validation, possible matches |
| Operations | `audit_logs` | admin actions (no secrets or student personal data) |

Raw retrieved bytes are stored outside the database in `backend/data/snapshots/<sha256>` (content-addressed, so
unchanged pages are stored once).

## Migrations

```bash
cd backend
.venv/Scripts/python -m app.cli migrate                    # alembic upgrade head
# after changing models.py:
.venv/Scripts/python -m alembic revision --autogenerate -m "describe change"
```

## PostgreSQL

Set `DATABASE_URL=postgresql+psycopg://user:pass@host/dbname`, `pip install "psycopg[binary]"`, then run
`python -m app.cli init`. No SQLite-specific SQL is used in the application code; SQLite pragmas are applied only when
the URL starts with `sqlite`.

## Backups (local procedure)

SQLite runs in WAL mode, so copy with the online backup API rather than copying the file while the API is running:

```bash
cd backend
.venv/Scripts/python -c "import sqlite3; s=sqlite3.connect('scholarscope.db'); d=sqlite3.connect('backup-scholarscope.db'); s.backup(d); d.close()"
# also archive data/snapshots/ (raw documents) if you need to re-inspect old retrievals
```

Restore by stopping the API and replacing `scholarscope.db` with the backup. For PostgreSQL use `pg_dump`/`pg_restore`.
