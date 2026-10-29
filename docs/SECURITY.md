# Security controls

| Area | Control | Where |
|---|---|---|
| Secrets | `.env` only (gitignored); `.env.example` has no values; API keys used only server-side | `core/config.py` |
| Passwords | scrypt (n=2¹⁴, r=8, p=1) with random salt; constant-time comparison; ≥10 characters | `core/security.py` |
| Sessions | HS256 JWT (12 h), `SECRET_KEY` ≥32 chars required in production (ephemeral key with warning in dev) | `core/security.py` |
| Authorization | Role checked server-side on every admin route (`require_admin` router dependency); students can only touch their own profile, answers and saved items | `api/deps.py`, routers |
| Input validation | Strict Pydantic models (`extra="forbid"`), vocabulary-checked codes, numeric ranges, URL scheme checks | `schemas.py` |
| Rate limiting | register 10/h, login 20/15 min, PDF check 10/h, manual source checks, dry runs and extraction | `core/ratelimit.py` (in-memory, single instance) |
| Uploads | Size cap (10 MB) read with a bound, `%PDF-` magic check, CSV extension check; uploads are parsed in memory and never written to a web-served path | `routers/me.py`, `routers/admin.py` |
| SSRF / malicious redirects | Fetch only registered sources' allowed URL patterns; every redirect re-validated; public IPs only; no credentials in URLs; size/time/redirect limits | `services/sources/fetcher.py` |
| Fixture paths | Resolved and confined to the fixtures directory (no traversal) | `fetcher._fetch_fixture` |
| SQL injection | SQLAlchemy ORM / parameterized statements only | everywhere |
| Rendering | React escapes all text; no `dangerouslySetInnerHTML`; external links only rendered for `http(s)` URLs with `rel="noopener noreferrer"` | `components/ui.tsx` `ExternalA` |
| Prompt injection | Untrusted document delimited; instruction to ignore embedded instructions; quote + sentence injection check; values never auto-applied | `extraction/extractor.py` |
| Errors and logs | Generic 500 body; logs contain method, path, status, timing and request id only (no bodies, tokens or query strings); audit log excludes personal data | `main.py`, `services/audit.py` |
| Headers / CORS | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`; CORS restricted to configured origins without credentials | `main.py` |
| Privacy | Minimal optional profile; no identity numbers or documents; account deletion cascades all student data | `models.py`, `routers/me.py` |
| Crawling ethics | robots.txt, identifiable UA, rate limits; 401/403/451 pause the source; no bypass of CAPTCHAs, logins or bot protection | `fetcher.py`, `orchestrator.py` |

## Known limitations

- The JWT is stored in `localStorage`, which an XSS bug could read. React escaping reduces the risk; an HttpOnly-cookie
  session with CSRF protection would be stronger for production.
- The rate limiter is per process and in memory; use a shared store (e.g. Redis) behind multiple instances.
- DNS rebinding between the SSRF check and the connection is not fully prevented (resolution happens twice).
- There is no admin 2FA and no password-reset flow.
- Production deployment: run `uvicorn` behind a reverse proxy with TLS (e.g. `uvicorn app.main:app --workers 1
  --proxy-headers` with `SCHEDULER_ENABLED=true` on exactly one instance); never use `--reload` in production. Set
  `APP_ENV=production` (disables `/docs`).
