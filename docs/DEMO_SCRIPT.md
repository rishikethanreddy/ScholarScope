# Demonstration script

Two ways to demonstrate. **Live** uses the real database and real websites; **offline** uses a separate demo database
whose sources are clearly labelled local fixtures (a banner says so on every page). Never present an offline run as
live scraping.

## Offline demo (reproducible; also automated)

```bash
sh e2e/reset_demo.sh      # fresh backend/data/demo/demo.db + admin@demo.local / demo-admin-pass-1
# Terminal 1: start the demo API with the environment variables the script prints
# Terminal 2: cd frontend && npm run dev
backend/.venv/Scripts/python e2e/demo_scenario.py   # optional: runs all steps below with assertions and screenshots
```

| # | Do this | What it shows |
|---|---|---|
| 1 | Sign in as admin → **Operations → Sources** | Registry; fixture sources labelled "Local fixture (not live)" |
| 2 | **Run check** on "NSP listing — archived copy" → **View job** | Job log: 31 schemes parsed; 5 deadlines `2026-09-30 -> 2026-10-31` auto-accepted; 4 candidates |
| 3 | **Review queue** → *National Means Cum Merit Scholarship* | Candidate fields with source evidence snippets |
| 4 | Clear *Provider* and click **Approve & publish** | Validation refuses: "Missing required field: provider" |
| 5 | (Optional, needs LLM key) **Run AI extraction on document** | Quote-verified fields; rejected values listed with reasons |
| 6 | Fill provider, education levels `PRE_MATRIC, POST_MATRIC_SCHOOL`, income rule `limit`, ceiling `350000`; approve | Record published, "Discovered by monitor"; edited fields recorded as admin evidence |
| 7 | Sign out; **Create account**; profile: School up to Class 10, class 9, income 200000, Bihar, citizen, none of the special circumstances | Dashboard with outcome counts, missing information and deadlines |
| 8 | Discover → search "means" → open NMMS → **Why this match** | Each rule with your value, the rule and evidence ("Entered by admin") |
| 9 | Run `python -m app.cli demo-revision --n 2` (with demo env vars); as admin run the NSP check again | Pragati degree deadline `2026-10-31 -> 2026-11-15` auto-accepted; MNRE fellowship "no longer listed" queued |
| 10 | Open AICTE Pragati (Technical Degree) → **History** | v1 (dataset, 31 Oct) kept; v2 15 Nov "(was 31 Oct 2026)" |
| 11 | **Operations → Changes** | The removal waits for review (not auto-applied) |
| 12 | Run check on "Unreachable source" | Job failed `not_found`; source shows *degraded*; nothing invented |
| 13 | Run check on "Tata Trusts grants page" | Closure statement found and queued; record shows *Needs review* |
| 14 | **What changed?** page and the student dashboard | Applied changes, newly discovered schemes, "new opportunities for me" |

Reset afterwards with `python -m app.cli demo-revision --n 1` or `sh e2e/reset_demo.sh`.

## Live demo (real sources)

Uses `backend/scholarscope.db`. Run **Operations → Sources → Test** on `nsp_all_schemes` (dry run against the real
site), then **Run check**. Expect "0 changes" if nothing changed since the last check. That is the honest, correct
outcome; say so. Show the job log, **Last checked** vs **Last verified** on a record, and the Tata Trusts closure
statement waiting in the Changes queue.
