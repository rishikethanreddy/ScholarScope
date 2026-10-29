# ScholarScope AI — evaluation results

Generated 2026-10-20T12:25:00.760053+00:00.

> All gold labels were produced by the developer (an AI assistant) from archived sources and are documented in evaluation/gold/*.json. They have not yet been independently verified by a human; treat results as preliminary.


## E1. NSP listing parser accuracy

Deterministic parser vs. labelled values for every scheme row, on the real archived page and on synthetic markup perturbations.

*Data:* snapshots/nsp_all_scholarships_2026-10-18.html; gold/nsp_listing_fields.json

| Metric | Proposed | n |
|---|---|---|
| archived page (real): schemes parsed | 31 |  |
| archived page (real): field accuracy (open date, deadline, renewal flag) | 1.0 | 93 |
| whitespace reformatted (synthetic): schemes parsed | 31 |  |
| whitespace reformatted (synthetic): field accuracy (open date, deadline, renewal flag) | 1.0 | 93 |
| class order changed (synthetic): schemes parsed | 31 |  |
| class order changed (synthetic): field accuracy (open date, deadline, renewal flag) | 1.0 | 93 |
| extra wrapper elements (synthetic): schemes parsed | 31 |  |
| extra wrapper elements (synthetic): field accuracy (open date, deadline, renewal flag) | 1.0 | 93 |

- Limitation: Single real snapshot; real future layout changes may differ from the synthetic perturbations.

- Limitation: Gold labels were read by the developer from the same page; perfect scores mainly show the parser is faithful, not that it generalises.

## E2. Entity resolution / duplicate detection

Linking NSP listing schemes to dataset records. Baseline = name similarity alone (same 0.86 threshold, no discriminator words, no URL/provider signals). An exact-normalized-name baseline is in extra.

*Data:* 31 schemes on the archived NSP page; gold/entity_resolution.json (28 schemes present in the dataset, 3 absent)

| Metric | Proposed | Baseline | n |
|---|---|---|---|
| Auto-match precision | 1.0 | 1.0 | 31 |
| Auto-match recall | 0.964 | 0.964 | 31 |
| Auto-match F1 | 0.982 | 0.982 | 31 |
| Wrong automatic merges | 0 | 0 | 31 |
| Sent to human review | 1 | 0 | 31 |

Extra: `{"exact_name": {"precision": 1.0, "recall": 0.857, "f1": 0.923, "wrong_merges": 0, "deferred": 0, "tp": 24}}`

- Limitation: Small n (31). Precision is prioritised over recall by design: uncertain pairs go to review.

## E3. Change detection: material vs cosmetic

10 labelled revisions of the real NSP page (3 cosmetic, 6 material, 1 new scheme) run through the full pipeline from a fresh database each time, plus 6 labelled HTML page variants for the generic page monitor. Baseline = whole-page byte-hash comparison.

*Data:* Synthetic revisions derived from snapshots/nsp_all_scholarships_2026-10-18.html (defined in evaluation/run.py)

| Metric | Proposed | Baseline | n |
|---|---|---|---|
| Field-level change precision | 1.0 | not supported | 7 |
| Field-level change recall | 1.0 | not supported | 7 |
| Field-level change F1 | 1.0 | not supported |  |
| Revision-level alert precision (listing) | 1.0 | 0.6 | 10 |
| Revision-level alert recall (listing) | 1.0 | 1.0 |  |
| Cosmetic revisions raising a material alert | 0 | 3 | 3 |
| New scheme candidates created for R10 | 1 | not supported |  |
| Page monitor: material-change precision | 1.0 | 0.333 | 6 |
| Page monitor: material-change recall | 1.0 | 1.0 |  |

- Limitation: Revisions are synthetic edits of a real page; they test the mechanism, not the real-world rate of changes.

- Limitation: Byte-hash baseline cannot localise which field changed, so field-level metrics do not apply to it.

## E4. Eligibility classification

Proposed three-valued engine vs. the project's original v1 engine (baseline) on labelled persona x real-record cases. Extra: ablation of the proposed engine that treats unknown as satisfied.

*Data:* gold/eligibility_cases.json: 38 cases ({'undetermined': 12, 'not_eligible': 24, 'eligible': 2}), 6 synthetic personas, 23 real records

| Metric | Proposed | Baseline | n |
|---|---|---|---|
| 3-class accuracy | 1.0 | 0.158 | 38 |
| False-positive eligibility rate | 0.0 | 0.861 | 38 |
| Wrongful exclusion rate | 0.0 | 0.071 | 38 |
| Undetermined cases flagged as undetermined | 1.0 | 0.0 | 38 |

Extra: `{"unknown_as_satisfied_ablation": {"3-class accuracy": 0.684, "False-positive eligibility rate": 0.333, "Wrongful exclusion rate": 0.0, "Undetermined cases flagged as undetermined": 0.0}, "error_analysis": {"undetermined_by_unknown_reasons": {"needs_confirmation": 4, "scholarship_unresolved": 3, "needs_confirmation+scholarship_unresolved": 1, "needs_confirmation+scholarship_unresolved+student_missing": 1, "student_missing": 3}, "not_eligible_by_first_failed_criterion": {"Beneficiary group": 4, "Disability": 1, "Education level": 7, "State / domicile": 2, "Family income": 4, "Year of study": 1, "Course / discipline": 3, "Category": 2}}}`

- Limitation: Labels were written by the developer who also wrote the rules: risk of shared interpretation. A human-labelled set is needed before claiming accuracy.

- Limitation: The v1 baseline has no 'undetermined' output, so its undetermined recall is 0 by construction; false-positive eligibility is the fairest comparison.

## E5. Freshness ablation: static dataset vs. monitored data

On 2026-10-18, which application windows does each variant show correctly, using the official NSP listing archived that day as ground truth? B0 = dataset status text, B1 = static dataset dates, Proposed = dates after one monitored check (deterministic parser, auto-accepted under policy).

*Data:* 28 dataset records that appear on the archived NSP listing; job succeeded

| Metric | Proposed | Baseline | n |
|---|---|---|---|
| Deadline equals official listing | 1.0 | 0.821 | 28 |
| Open/closed status correct | 1.0 | 0.821 | 28 |
| Records wrongly shown as closed | 0 | 5 |  |
| Actionable matches hidden as 'closed' (6 personas) | 0 | 4 | 19 |

Extra: `{"b0_status_text_accuracy": 1.0, "wrongly_closed_static": ["IND-NSP-008", "IND-NSP-009", "IND-NSP-014", "IND-NSP-025", "IND-NSP-029"], "note_b0": "B0 marks every record ACTIVE. It is right for these NSP records only because all of them happen to be open; it is wrong for the Tata Trusts record, whose official page said on 2026-10-18 that the programme is closed for 2026-27 (observed by the page monitor, pending review), and it has no notion of passed deadlines."}`

- Limitation: One snapshot date. Ground truth is the official listing, which can itself be wrong or late.

- Limitation: Covers only records present on the NSP listing (private schemes are not in this ground truth).

## E6. AI extraction accuracy (quote-verified)

The configured LLM extracts fields from 3 archived official documents; values without a verbatim, context-appropriate quote are rejected before scoring. Pooled over every archived run in results/e6_runs.jsonl (each document scored each time the provider was available).

*Data:* gold/extraction.json (3 documents, hand-checked); 3 archived runs; 5 scored document-runs; 4 document-runs lost to provider errors

| Metric | Proposed | n |
|---|---|---|
| Field accuracy (pooled) | 0.952 | 21 |
| Documents scored at least once | 3 | 3 |
| Hallucinated values where the document states nothing | 1 | 8 |
| Model values rejected by quote/context validation | 5 |  |
| Document-runs lost to provider errors (HTTP 503 overload or 429 quota) | 4 | 9 |
| Mean seconds per scored document | 23.85 | 4 |

- Limitation: Three documents only; LLM output is non-deterministic and provider availability varied between runs.

- Limitation: Cost per document was not metered.

## E7. Operational metrics (live database)

Counts from the real crawl history of this installation (real network checks).

*Data:* scholarscope.db; jobs {'succeeded': 9}

| Metric | Proposed | n |
|---|---|---|
| Source-check success rate | 1.0 | 9 |
| Changes auto-accepted under policy | 14 |  |
| Changes waiting for review (manual-review load) | 0 |  |
| Candidates with failed AI extraction | 1 | 4 |
| Change-detection latency | not measured |  |
