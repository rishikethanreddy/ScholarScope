# Sources, connectors and crawler policy

## Registered sources (checked manually on 2026-10-18 before registration)

| Key | Source | Class | Connector | Every | Notes |
|---|---|---|---|---|---|
| `nsp_all_schemes` | NSP "All Scholarships" listing | official | `nsp_listing` | 6 h | Server-rendered; robots.txt 404 (no rules published); no ETag, `Cache-Control: no-store`; no API or sitemap found |
| `aicte_swanath_guideline` | AICTE Swanath guideline PDF on NSP | official | `pdf_document` | 7 d | Text layer present; supports ETag/Last-Modified; AI extraction on change |
| `depwd_post_matric` | DEPwD post-matric scholarship page | official | `html_page` | 1 d | AI extraction on change |
| `tata_trusts_education_grants` | Tata Trusts education grants page | official (scheme owner) | `html_page` | 1 d | robots.txt disallows only `/manage`; closure statement detected live |
| `reliance_scholarships_release` | Reliance Foundation 2026-27 announcement | official (scheme owner) | `html_page` | 1 d | robots.txt disallows `/core/`, `/profiles/` only |
| `reliance_scholarships_portal` | Reliance scholarships portal | official | `html_page` | — | **Disabled**: content is rendered client-side; browser rendering is not configured |

Aggregators (e.g. Buddy4Study) are **not** registered. If added, they must use classification `aggregator`; their
observations rank below official sources and are never auto-accepted.

## Crawler policy (enforced in `app/services/sources/fetcher.py`)

- Only URLs matching the source's `allowed_url_patterns` are fetched, including every redirect hop.
- Hosts must resolve to public IP addresses (blocks loopback, private, link-local and metadata addresses).
- `robots.txt` is honoured per RFC 9309: 4xx ⇒ allowed; 5xx/unreachable ⇒ treated as disallowed for now.
- Identifiable User-Agent (`CRAWLER_USER_AGENT`), one request at a time per host, ≥3 s between requests.
- Retries with exponential backoff and jitter on 429/5xx/timeouts; `Retry-After` honoured (>120 s ⇒ give up and
  reschedule); conditional requests with stored ETag/Last-Modified; 304 recorded as unchanged.
- Limits: 25 s timeout, 15 MB body, 5 redirects.
- **401/403/451 ⇒ `access_denied`, source paused.** No CAPTCHA solving, login automation, proxy rotation or stealth
  techniques are used, ever. The legitimate alternative is to contact the source or enter data manually via review.
- One active job per source (DB check + in-process lock). Jobs interrupted by a restart are marked failed at startup.

## Source health

`healthy` → `degraded` (1–4 consecutive failures) → `failing` (≥5; still retried with backoff up to 24 h).
`paused` (access denied, policy block, or admin) requires an explicit **Resume**. Backoff:
`min(24 h, 2^failures × interval / 4)`, or `Retry-After` if larger. Recently changed sources are checked at half
their normal interval (freshness policy).

## Connectors

| Connector | Input | Output |
|---|---|---|
| `nsp_listing` (`nsp-listing/1.0`) | NSP listing HTML | Per scheme: title, ministry, open date, student deadline, renewal-only flag, guideline/FAQ links. Matched schemes → field observations; unmatched → candidates; vanished schemes → `listing_presence` change for review. Parsing 0 schemes, or fewer than 50% of the previous count, fails the job (parser anomaly) instead of reporting "no changes". |
| `html_page` / `pdf_document` (`page-monitor/1.0`) | One or more page/PDF URLs, optionally linked to one record | Baseline on first fetch; byte-identical ⇒ unchanged; same normalized main text ⇒ cosmetic (informational); different text ⇒ material `page_content` change with a diff. Deterministic rules record deadline statements (only if exactly one distinct date) and closure statements. Optional AI extraction creates an update candidate. |

## How to add a new source

1. Check the site manually: terms, robots.txt, whether content is server-rendered (view source), whether an official
   feed/API exists. Record findings in *Access-policy notes*.
2. **Operations → Sources → Add source** (or add it to `config/sources.json` and run `python -m app.cli seed-sources`).
   Set the narrowest allowed URL pattern that covers the target and its redirects.
3. Click **Test** (dry run, nothing stored) and check the parsed output / extracted text quality.
4. Click **Run check**. The first check of a page monitor only captures a baseline.
5. For a new site layout that is a listing of many schemes, write a new parser module alongside
   `connectors/nsp_listing.py`, register it in `crawl/orchestrator.CONNECTORS`, add the archived page to
   `tests/fixtures/` and a parser test.

## How to rerun the crawler

```bash
python -m app.cli crawl --source nsp_all_schemes   # one source
python -m app.cli crawl --due                      # whatever the scheduler would run now
python -m app.cli crawl --all                      # every enabled source
```
