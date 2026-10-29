# ScholarScope AI

**A freshness-aware, evidence-grounded scholarship discovery and explainable recommendation system.**

ScholarScope monitors registered official scholarship sources, keeps field-level evidence and a version history for
every record, and tells each student, rule by rule, whether they meet a scholarship's *recorded* criteria. It never
treats unknown information as a pass.

> Academic project. Results are guidance based on recorded criteria, not official decisions. Coverage is limited to
> the registered sources and the imported dataset.

## What works (verified 2026-10-18)

| Capability | Status | Evidence |
|---|---|---|
| Dataset import with normalization, interpretation report, evidence and versioning | Working | `tests/test_import.py`; 31/31 rows imported |
| Live monitoring of the NSP scheme listing (scheduled + manual) | Working against the real site | 2 live runs: 5 stale deadlines corrected, 4 new schemes queued |
| HTML/PDF page monitors with cosmetic-change filtering and closure/deadline rules | Working | Tata Trusts closure statement detected live |
| Safe fetcher: allowlist, SSRF guard, robots.txt, rate limit, retries, Retry-After, conditional GET, size/redirect limits | Working | `tests/test_fetcher.py` (21 cases) |
| Entity resolution with discriminator words; uncertain pairs go to human review | Working | E2: precision 1.0, 0 wrong merges |
| Change detection, materiality, auto-accept policy, version history | Working | E3: 7/7 labelled changes, 0 cosmetic false alarms |
| Three-valued eligibility, missing-info questions, separate relevance score | Working | `tests/test_eligibility.py`; E4 |
| AI extraction (Gemini/Anthropic) with quote verification and prompt-injection checks | Working with a configured key; fails clearly without one | E6: 20/21 fields over 3 archived runs; 1 misattributed value passed validation (see docs/EVALUATION.md) |
| Admin review (approve/link/reject candidates, accept/reject changes), audit log | Working | `tests/test_api.py`, e2e scenario |
| Student UI: profile, dashboard, discover, why-this-match, verify, history, saved, change feed | Working | Playwright e2e (11 checkpoints) |
| JWT auth with student/admin roles, rate limits, upload limits | Working | `tests/test_api.py` |

Known gaps are listed in [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md#limitations).

## Quick start (Windows, Git Bash or PowerShell; macOS/Linux use `.venv/bin/python`)

Requirements: Python 3.12+ and Node 20+.

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
cp .env.example .env                      # then set SECRET_KEY (and optionally LLM_API_KEY)
.venv/Scripts/python -m app.cli init      # migrate, import bundled dataset, seed sources
ADMIN_PASSWORD='choose-a-long-password' .venv/Scripts/python -m app.cli create-admin --email you@example.com
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# Frontend (new terminal)
cd frontend
npm install
cp .env.example .env
npm run dev                                # http://localhost:5173
```

The scheduler starts with the API and checks sources when they are due (NSP every 6 h). Run a check immediately with
`python -m app.cli crawl --source nsp_all_schemes` or from **Operations → Sources → Run check**.

API docs: http://localhost:8000/docs (disabled when `APP_ENV=production`).

## Offline demonstration

A separate demo database uses clearly labelled local fixtures (an archived copy of the real NSP page, a synthetic
revision, and a deliberately broken source). See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

```bash
sh e2e/reset_demo.sh        # builds backend/data/demo/demo.db and admin@demo.local
# start the API with the env vars the script prints, then the frontend, then:
backend/.venv/Scripts/python e2e/demo_scenario.py     # automated 14-step scenario with screenshots
```

## Tests and evaluation

```bash
cd backend && .venv/Scripts/python -m pytest -q          # 100 offline tests (network tests skipped)
cd backend && .venv/Scripts/python -m pytest -q -m network   # live smoke tests against real sources
cd frontend && npm run build && npx oxlint src           # type-check, build, lint
backend/.venv/Scripts/python -m evaluation.run [--llm]   # from project root; writes evaluation/results/
```

## Project layout

```
backend/
  app/
    api/            routers (auth, public, me, admin), dependencies, serializers
    core/           config, security (scrypt + JWT), rate limiting
    services/
      ingestion/    CSV import
      sources/      safe fetcher
      connectors/   nsp_listing parser + connector, page_monitor (HTML/PDF), shared storage
      crawl/        orchestrator (jobs, health, backoff) and scheduler
      extraction/   text extraction, provider-agnostic LLM client, quote-verified extractor
      recommendation/ eligibility (three-valued), scoring, engine (ranking, snapshots)
      matching.py   entity resolution / duplicates     records.py  evidence, change events, versions
      trust.py      verification status, freshness    review.py   candidate and change review
      normalize.py  vocabulary-driven normalization    audit.py    audit log
    models.py, schemas.py, cli.py, demo.py, main.py
  config/           vocabulary.json, policies.json, scoring_config.json, sources.json
  migrations/       Alembic
  tests/            pytest suite + fixtures (incl. archived real NSP page)
frontend/src/       React + TypeScript + Tailwind (pages/, components/, lib/)
evaluation/         gold labels, archived snapshots, baselines, run.py, results/
e2e/                Playwright scenario and demo reset script
docs/               design, operations and research documentation
_legacy/            the original v1 code and database, kept for reference and as an evaluation baseline
```

## Documentation

| Topic | File |
|---|---|
| Stage-1 audit, dataset quality, plan | [docs/AUDIT_AND_PLAN.md](docs/AUDIT_AND_PLAN.md) |
| Architecture and data flow | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Database schema, migrations, backups, PostgreSQL | [docs/DATABASE.md](docs/DATABASE.md) |
| API reference | [docs/API.md](docs/API.md) |
| Sources, connectors, crawler policy, adding a source | [docs/SOURCES.md](docs/SOURCES.md) |
| Dataset data dictionary and import | [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) |
| AI extraction and validation | [docs/AI_EXTRACTION.md](docs/AI_EXTRACTION.md) |
| Eligibility and recommendation algorithm | [docs/RECOMMENDATION.md](docs/RECOMMENDATION.md) |
| Evidence, freshness and trust model | [docs/TRUST_MODEL.md](docs/TRUST_MODEL.md) |
| Security controls | [docs/SECURITY.md](docs/SECURITY.md) |
| Evaluation methodology and results | [docs/EVALUATION.md](docs/EVALUATION.md) |
| Demo script | [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) |
| Troubleshooting | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| Final report, novelty, viva preparation | [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md) |
