# ScholarScope AI — Stage 1 audit and implementation plan

Audit date: 2026-10-18. A backup of the pre-change project (without `.env` files and virtualenvs) is at
`../scholarship-recommender-baseline-2026-10-18.zip`.

## A. Current-state audit

| Area | Found | Assessment |
|---|---|---|
| Backend | FastAPI, SQLAlchemy, SQLite (`scholarships.db`), 5 routers | Reusable foundation. No auth, `allow_origins=["*"]` with credentials, no input limits. |
| Data model | `dataset_versions`, `scholarships` (flat strings), `students` | No provenance, no history, no source registry, no jobs. Lists stored as free text. |
| Import | `csv_parser.py` (pandas) | **Bug:** `minimum_cgpa_or_percentage` copied into *both* `minimum_cgpa` and `minimum_percentage`, so "60%" becomes "CGPA ≥ 60". Every row stored as `APPROVED`. `num_valid` always equals `num_records`. |
| Eligibility | `eligibility.py` | Missing student data is recorded but the student is still `is_eligible=True`; category, education level and course never fail; states and disability are not checked. Effectively "unknown ⇒ eligible". |
| Scoring | `scoring.py` | Score only computed for eligible rows; constant filler points (category always 80). Not explained per factor. |
| AI | `services/ai/extractor.py` (Gemini SDK) | **Returns hard-coded mock data** when the key is missing *or* the call fails, and the API returns it as if extracted. Prompt says "guess reasonably". No evidence, no prompt-injection guard, no size limit. `ai_error.log` shows 404 model-retired, 429 quota, schema failures, DNS failures. |
| Frontend | React 19, Vite 8, TS 6, Tailwind 4, framer-motion, lucide | Six pages work against the API. `any` everywhere, `str` type typo in `api.ts`, no auth, no admin, student identity = UUID in the URL. |
| Tests / migrations / docs | None (Alembic listed but not configured) | — |
| Secrets | `backend/.env` holds a real Gemini key; `frontend/.env` holds the API URL | Kept; added `.gitignore` and `.env.example`. |
| Unrelated files | Two `dotstumps_*.jpg` cricket-app images in the parent folder | Ignored. |

## B. Dataset-quality report (`india_scholarship_dataset_2026_27_researched.csv`)

- 31 rows × 41 columns, UTF-8, IDs `IND-NSP-001…029` (020 absent) and `IND-PRI-001…003`. No duplicate IDs or names.
- Coverage: 28 government, 3 private foundation. 29 "All India", 2 region-restricted.
- `minimum_cgpa_or_percentage`: 21 `UNKNOWN`, 3 free-text ("Scheme/norm dependent", "Programme-specific", "Programme admission merit"), 5 × `60` (%), 1 × `7.5` (CGPA), 1 × `80` which `minimum_marks_details` shows is the **80th percentile**, not 80 %.
- `maximum_family_income`: 10 explicit "NO INCOME CEILING STATED", 4 `UNKNOWN`, 17 numeric (₹2.5 L – ₹25 L, annual).
- `category`: 20 `ANY`, 6 "Government reservation norms" (a selection note, not an exclusive restriction), 5 explicit restrictions.
- `education_level`: 13 inconsistent labels (Degree / UG / Higher Education / Post-Matric / School/UG …) → needs a controlled vocabulary.
- Dates: all ISO except 2 `UNKNOWN` (Tata Trusts). `application_status` is `ACTIVE` for all 31, but **7 deadlines (5 × 2026-09-30, 2 × 2026-10-05) are already past** on the audit date, so status is stale. *(Corrected 2026-10-20: the first version of this audit said 6.)*
- `source_last_verified` = 2026-09-01 for every row (one bulk research date, not per-field verification).
- 12 rows use the NSP listing page itself as `official_source_url` rather than a scheme guideline.
- Live comparison (NSP `All-Scholarships`, fetched 2026-10-18): NSP lists **31-10-2026** for 5 schemes the dataset records as 2026-09-30, and lists 3 schemes absent from the dataset (UGC PG Scholarship, Ishan Uday, NMMS).

## C. Competitor and research-gap assessment (preliminary; revisited in `docs/FINAL_REPORT.md`)

- **NSP** (official): authoritative listing of central schemes with open/close dates and guideline PDFs; no personalised matching, no change history, no explanation.
- **Buddy4Study** (aggregator): profile-based matching and "follow" alerts that include deadline-extension updates (documented on its listing pages). Aggregator, not an authority; matching method undocumented.
- **Research**: scholarship recommenders in the literature are mostly classifiers (SVM, RF), fuzzy or expert systems that judge eligibility from a static dataset. Web-change-detection work (Vi-DIFF, WebEvo) separates content changes from layout changes, but not in the context of eligibility-relevant fields.
- **Selected gap (hypothesis):** none of the above *publicly documents* combining (1) field-level provenance with retrieval time, (2) material/cosmetic change history for eligibility fields, and (3) three-valued eligibility that never treats unknown as satisfied, plus (4) a measured comparison of static and freshness-aware data. Deadline alerts alone are **not** novel.

## D. Architecture (modular monolith)

```
React SPA ──HTTP/JSON──► FastAPI
                          ├─ api/routers  (auth, students, scholarships, recommendations, feed, admin/*)
                          ├─ core         (config, security/JWT, rate limit, logging)
                          ├─ services
                          │   ├─ ingestion   CSV → normalized record + field evidence + version
                          │   ├─ sources     registry, safe fetcher (allowlist, SSRF guard, robots, rate limit, retries, conditional GET)
                          │   ├─ connectors  nsp_listing · html_page · pdf_document (each also runnable on local fixtures)
                          │   ├─ crawl       orchestrator (job lock, health, auto-pause) + background scheduler thread
                          │   ├─ matching    entity resolution / duplicate detection
                          │   ├─ changes     field diff, materiality, auto-accept policy, versioning
                          │   ├─ extraction  HTML/PDF text, provider-agnostic LLM, schema + evidence validation
                          │   ├─ review      candidate approval / publication
                          │   ├─ trust       freshness policy + verification status
                          │   └─ recommendation  three-valued eligibility, scoring, explanations, snapshots
                          └─ SQLite (PostgreSQL-ready via DATABASE_URL), Alembic migrations, snapshots on disk
```

## E. Prioritized backlog

1. Schema v2 + Alembic, normalization vocabulary, CSV import with evidence and import report. (Stage 2)
2. Three-valued eligibility, configurable scoring, explanations, missing-info list. (Stage 3)
3. Source registry, safe fetcher, NSP listing connector, generic HTML and PDF monitors, scheduler, job history. (Stage 4)
4. Entity resolution, change events, versions, freshness and trust statuses. (Stage 5)
5. LLM extraction with evidence verification, candidate review and publication. (Stage 6)
6. Student UI (auth, profile, dashboard, discover, detail with why, missing info, verify, history; saved/tracker; feed) and admin UI. (Stage 7)
7. Auth/roles, audit log, rate limiting, upload limits, tests, evaluation, docs. (Stage 8–9)

## F. Test and evaluation plan

- Unit tests: normalization, dates, dedup, eligibility boundaries, unknowns, scoring, change detection, fetcher failure modes (MockTransport), LLM schema/evidence validation, conflicts, auth.
- Integration: API tests with an in-memory DB and fixture sources; network tests marked `network` and skipped by default.
- Evaluation (`evaluation/`): NSP parser accuracy on an archived real snapshot; entity-resolution precision/recall against hand-labelled mapping; change-detection P/R/F1 on labelled fixture revisions; eligibility accuracy and false-positive-eligible rate vs. the legacy engine on labelled profile × scholarship pairs; freshness ablation (static dataset vs. live-updated deadlines) against the live official listing.

## G. Risks, assumptions, external dependencies

- NSP markup can change at any time; the parser is versioned and fails loudly (zero rows ⇒ job fails, no silent "no changes").
- NSP sends `Cache-Control: no-store` and no ETag, so change detection relies on content hashes.
- The configured Gemini key has a history of quota/model-retirement errors; extraction must work as a clearly failed state with a manual path.
- Gold labels in `evaluation/` were created by the developer (AI assistant) from archived snapshots and must be spot-checked by a human before being cited.
- Not a git repository; the backup zip is the baseline.
