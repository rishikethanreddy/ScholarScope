# API reference

Interactive OpenAPI docs: `http://localhost:8000/docs`. All bodies are JSON unless noted. Authenticated routes need
`Authorization: Bearer <token>` from `/api/auth/login` or `/api/auth/register`. Admin routes return 403 for students.

## Public

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | DB check, scheduler state, demo flag |
| GET | `/api/meta/vocabulary` | controlled vocabularies, trust status labels, freshness policy |
| GET | `/api/stats/public` | counts computed from the DB; LLM configuration flag |
| GET | `/api/scholarships` | filters: `q`, `education_level`, `provider_type`, `availability`, `verification_status`, `state`, `sort` |
| GET | `/api/scholarships/{id}` | record, trust status + flags, current and historical evidence, linked sources, changes, versions |
| GET | `/api/scholarships/{id}/versions/{n}` | full snapshot of a past version |
| GET | `/api/feed/changes?days=30` | applied material changes and newly published (crawler-discovered) records |

## Auth (rate-limited)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/register` | `{email, password}` (≥10 chars); 10/hour per IP |
| POST | `/api/auth/login` | 20 per 15 min per IP |
| GET | `/api/auth/me` | current user + `has_profile` |

## Student (`/api/me`)

| Method | Path | Notes |
|---|---|---|
| GET/PUT | `/profile` | strict schema (unknown fields rejected; no identity numbers accepted) |
| DELETE | `/account` | deletes user and all profile data |
| GET | `/recommendations` | all records evaluated; `counts`, `missing_profile_fields`, `updates` (since last acknowledgement) |
| POST | `/updates/acknowledge` | store a new baseline for "what changed for me" |
| GET | `/recommendations/{scholarship_id}` | one evaluation with criteria, evidence, relevance factors, answers |
| PUT | `/answers` | `{scholarship_id, criterion_key, answer: yes|no|unsure}` |
| GET/POST | `/saved` · PATCH/DELETE `/saved/{id}` | bookmarks and application status |
| POST | `/check-document` | multipart PDF ≤10 MB; AI-extracted and evaluated, nothing stored; 503 if no LLM is configured |

## Admin (`/api/admin`)

| Area | Endpoints |
|---|---|
| Overview | `GET /overview` |
| Sources | `GET/POST /sources`, `PATCH /sources/{id}`, `POST /sources/{id}/check`, `/pause`, `/resume`, `/test` (dry run) |
| Jobs | `GET /jobs?status=&source_id=`, `GET /jobs/{id}` (log + documents), `POST /jobs/{id}/retry` |
| Documents | `GET /documents/{id}` |
| Candidates | `GET /candidates?status=`, `GET /candidates/{id}`, `POST /candidates/{id}/approve` (`{payload?, note?}`), `/reject`, `/link` (`{scholarship_id}`), `/extract` |
| Changes | `GET /changes?status=pending|auto_accepted|accepted|rejected|informational|all`, `POST /changes/{id}/accept`, `/reject` |
| Data | `GET /quality`, `GET /datasets`, `POST /datasets/import` (multipart CSV, `version`, `dataset_name`, `mode=review|apply`) |
| Records | `POST /scholarships/{id}/publish?published=true|false` |
| Audit / evaluation | `GET /audit`, `GET /evaluation` |

Errors use `{"detail": "..."}`; validation errors are 422; unexpected errors return a generic 500 without internals.
