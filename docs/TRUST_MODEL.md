# Evidence, freshness and trust model

## Field-level evidence

Every observation of a field is a `field_evidence` row: value, source key/URL/classification, snippet, location
(page, CSV line or listing row), retrieval time, extraction method, verification status, document id, record version.
Per (record, field, source) only the newest is `is_current`; older ones remain as history.

Verification status of an observation: `dataset_claim` (from the curated CSV, never checked by the monitor),
`source_checked` (observed on a source), `confirmed` (an official source re-observed the published value),
`admin_entered` (typed by a reviewer).

## Source precedence (`config/policies.json → source_precedence`)

official 100 · institutional 80 · manual (admin) 70 · curated dataset 50 · aggregator 30 · other 10. The engine shows
the highest-precedence current evidence; ties go to the most recent retrieval. Precedence is used for display. It
does **not** silently change published values: changes go through the change policy below.

## Change policy

Changes are classified as **material** (deadline, dates, renewal window, listing presence, income/academic/education/
discipline rules, amount, documents, URLs, conditions, categories, gender, states, disability, status statements,
page content), **minor**, or **cosmetic** (name formatting; page bytes changed but normalized main text identical).

A change is applied automatically only if **all** hold:
- the source is classified `official` (or `fixture` in the offline demo),
- the method is the deterministic `nsp_listing_parser`,
- the field is one of `deadline`, `open_date`, `renewal_type`, `official_source_url`,
- the change is not a removal (a source that stops stating a value is not evidence the value no longer applies).

Everything else (AI extraction, page-text rules, closure statements, vanished listings, dataset re-imports) is
`pending` until an admin accepts or rejects it. Applied changes create a new `scholarship_versions` row; the previous
value stays in the version history and in the change event (`old_value`).

## Verification status of a record

Derived from stored facts by `app/services/trust.py`. Several flags can hold at once; the primary status is the first
in this order:

| Status | Rule |
|---|---|
| Conflicting sources | two current official observations from different sources disagree on a field |
| Source unavailable | every official source linked to the record is failing, paused or disabled |
| Needs review | a material change for the record is pending |
| Stale observation | last successful check older than the freshness policy (below) |
| Deadline not verified | the deadline has never been observed by the monitor (dataset only) |
| Official source confirmed | the latest official deadline observation equals the published deadline |
| Official source checked | an official source was checked but did not confirm the current deadline |
| Aggregator / dataset only | no official evidence and no official source linked |

**Last checked** = last successful check of any linked source. **Last verified** = last time an official source
re-observed the published deadline. They are shown separately because a successful HTTP request does not verify
every field.

There is deliberately **no numeric trust/confidence score**: we have no validation data that would give such a number
a defensible meaning.

## Freshness policy (operational defaults, configurable)

| Situation | Maximum age of last successful check |
|---|---|
| Deadline within 14 days | 24 h |
| Open or upcoming | 7 days |
| Closed or no deadline | 30 days |

Sources that changed in the last 7 days are re-checked at half their normal interval. These values are engineering
defaults for this project, not universal truths.
