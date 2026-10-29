# Troubleshooting

| Symptom | Cause / fix |
|---|---|
| UI says "Cannot reach the ScholarScope API" | Backend not running on `VITE_API_BASE_URL` (default `http://localhost:8000`), or CORS: add the UI origin to `CORS_ORIGINS`. |
| Everyone is logged out after restarting the API | `SECRET_KEY` not set, so an ephemeral key was used. Set it in `backend/.env`. |
| `address already in use` on 8000/5173 | An old server is still running. Windows: `Get-NetTCPConnection -LocalPort 8000` then `Stop-Process -Id <pid>`. |
| `sqlite3.OperationalError: unable to open database file` | Wrong `DATABASE_URL` path. Under Git Bash use a Windows path (`pwd -W`), e.g. `sqlite:///C:/…/demo.db`. |
| Database is locked | Another process is writing (e.g. CLI crawl while the API runs). Retry; WAL mode and a 30 s timeout are configured. |
| A source job fails with `parser_anomaly` | The page structure changed or returned an error page. Run **Test** to see what was fetched; update the parser and its fixture test. Nothing was applied. |
| A source is `paused` with "Access denied" | The site returned 401/403/451. Do not try to bypass it. Check the site's terms; enter data manually via review or contact the provider; then **Resume**. |
| `robots_disallowed` | robots.txt forbids the path, or robots.txt returned 5xx (treated as disallowed). Wait or choose a permitted URL. |
| AI extraction "not_configured" | No `LLM_API_KEY`/`AI_API_KEY`. Extraction is optional; enter fields manually in the review form. |
| AI extraction `provider_error … 503` / `quota` | Provider overloaded or quota exhausted; retried twice automatically. Try later or switch `LLM_PROVIDER`/`LLM_MODEL`. |
| AI extraction returns few fields | Values without a verifiable quote are discarded on purpose; see "Rejected AI value" notes in the review form. Scanned PDFs (`needs_ocr`) are refused. |
| Scheduler not checking sources | `SCHEDULER_ENABLED=false`, the source is disabled or paused, or `next_check_at` is in the future (see **Sources**). Use **Run check** or `python -m app.cli crawl --due`. |
| A scholarship shows "Stale observation" | Its last successful check is older than the freshness policy. Check the source's health and run it. |
| Recommendations show many "potential match" | Profile fields are missing or scheme questions are unanswered. The dashboard lists which fields would resolve the most matches. |
| `npm run build` type errors | Run `npx tsc -b` for details; types live in `frontend/src/lib/types.ts`. |
| Tests touching the network fail | Network tests run only with `-m network`; a failure means a live source changed, not necessarily a code bug. |
