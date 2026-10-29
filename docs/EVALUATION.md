# Evaluation methodology and results

Reproduce: from the project root run `backend/.venv/Scripts/python -m evaluation.run` (add `--llm` for E6).
Outputs: `evaluation/results/latest.json` (also shown on **Operations → Evaluation**) and `evaluation/results/report.md`.
Inputs are archived snapshots (`evaluation/snapshots/`) and labelled files (`evaluation/gold/`). The offline
experiments do not depend on any website being online.

> **Label provenance.** All gold labels were produced by the developer (an AI assistant) from archived sources on
> 2026-10-18. Each gold file records how. They have **not** been independently verified by a human. Treat every number
> below as preliminary until a second person re-labels at least a sample.

## Results (run of 2026-10-18)

### E1. NSP listing parser: 31/31 schemes, 93/93 fields correct
Correct on the real archived page and on three synthetic markup perturbations (whitespace, class order, extra
wrappers). This shows the parser is faithful to the page; it does not prove robustness to future redesigns, which
the parser-anomaly guard (0 rows, or <50% of the previous count, fails the job) is meant to catch.

### E2. Entity resolution: precision 1.00, recall 0.96, 0 wrong merges (n=31)
27 of 28 true links were made automatically; the 28th (ST scholarship, renamed on NSP) was sent to human review, as
designed. The name-similarity-only baseline scored the same on this snapshot: the discriminator words did not change
any decision here (they prevented second-ranked confusions such as School vs College, which never ranked first).
**Honest reading: no measured advantage over the baseline on this data.**

### E3. Change detection: field-level P/R/F1 = 1.00/1.00/1.00 on 7 labelled changes; 0 of 3 cosmetic revisions alerted
Byte-hash baseline: revision-level precision 0.60 (alerts on all 3 cosmetic revisions) and no field localisation.
Generic page monitor on 6 labelled variants: precision 1.00 vs 0.33 for byte hashing, both with recall 1.00.
The revisions are synthetic edits of a real page, so this tests the mechanism, not real-world change rates.

### E4. Eligibility: 38 labelled persona × real-record cases (24 not eligible, 12 undetermined, 2 eligible)

| Metric | Proposed | Original v1 engine | Ablation: unknown = satisfied |
|---|---|---|---|
| 3-class accuracy | 1.00 | 0.16 | 0.68 |
| False-positive eligibility rate | **0.00** | **0.86** | 0.33 |
| Wrongful exclusion rate | 0.00 | 0.07 | 0.00 |
| Undetermined flagged as undetermined | 1.00 | 0.00 (no such output) | 0.00 |

The perfect score of the proposed engine must be read with the limitation that **the same developer wrote the rules
and the labels**, so they share an interpretation of the dataset text. The robust finding is the comparison: the v1
engine called 86% of not-eligible/undetermined cases "eligible", mainly because missing data and unchecked rules
were treated as passes. The ablation isolates the three-valued logic: with the *same* improved rules but unknown
treated as satisfied, the false-positive eligibility rate is 0.33 (every one of the 12 undetermined cases becomes
"eligible").

### E5. Freshness ablation: deadlines correct for 28/28 vs 23/28 with the static dataset
Using the official NSP listing archived on 2026-10-18 as ground truth, the static dataset showed 5 schemes
(IND-NSP-008, -009, -014, -025, -029) as **closed when they were open** (NSP had extended them to 31 Oct). Across six
personas, 4 of 19 actionable matches would have been hidden as closed. After one monitored check: 0. The status-text
baseline (all "ACTIVE") happens to be right for these NSP records, but is wrong for the Tata Trusts programme, whose
own page says it is closed for 2026-27.

### E6. AI extraction (Gemini, quote-verified): 20/21 fields over 3 archived runs; 1 misattribution passed validation
*Updated 2026-10-20; this supersedes the earlier "8/9, 0 hallucinations" figure, which came from unarchived runs.*
Runs are archived in `results/e6_runs.jsonl` and pooled. Across 3 runs on 3 documents (AICTE Swanath PDF, NMMSS PDF,
DEPwD page), 5 document-runs were scored (all 3 documents at least once) and 20 of 21 fields were correct. In one of
the 8 field instances where the document states nothing, the model gave a value: a minimum disability of 80 % for
Swanath, quoting a clause about a *parent's* disability. That quote passed every validation check. 5 values were
rejected by validation, and 4 of 9 document-runs were lost to HTTP 503/429. Mean 23.9 s per scored document.

### E7. Operations (live database, real network checks; as of 2026-10-20)
9 checks, 9 succeeded (one triggered by the scheduler). Four NSP retrievals over 18–20 Oct were byte-identical, and
every listing check after the first reported zero changes. 14 changes were auto-accepted; 0 are pending (an admin
accepted the Tata Trusts closure). 1 candidate has a failed extraction. Change-detection latency is **not
measured**, because the true time a source changed is unknown.

## Not measured (and why)

- Precision@K / Recall@K for ranking: no student relevance judgements exist.
- Discovery recall over "all scholarships": no ground truth of the full universe; coverage is limited by design.
- Cost per document: provider usage was not metered.
- Duplicate-detection precision on the catalogue: `find_duplicate_pairs` returns no pairs on the current data, so there
  is nothing to score.

## Recommended next step

Have two people independently re-label `gold/eligibility_cases.json` and `gold/entity_resolution.json`, report
agreement (Cohen's κ), and re-run. Add a second NSP snapshot from a later date to test the parser over a real
time gap.
