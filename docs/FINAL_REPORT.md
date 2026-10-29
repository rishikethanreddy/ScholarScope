# ScholarScope AI: final report

*A Freshness-Aware, Evidence-Grounded Scholarship Discovery and Explainable Recommendation System.*
Report date: 2026-10-18. Measured results come from `evaluation/results/latest.json`; see
[EVALUATION.md](EVALUATION.md) for method and caveats.

## 1. Problem

Indian students find scholarships across a central portal (NSP), ministry and foundation pages, and aggregators.
Key facts change during a cycle (deadlines are extended, windows become renewal-only, programmes close), and
eligibility rules are scattered in PDFs. A static list goes stale quickly. On the audit date, the project's own
researched dataset (verified 2026-09-01) showed 5 NSP schemes as closed that NSP had extended to 31 October, and a
Tata Trusts programme as active although its page said it was closed. A recommender built on such data can hide open
opportunities or advertise closed ones, and a recommender that treats missing information as a pass gives false hope.

## 2. Existing approaches (what could be verified)

| System | Documented capabilities (source) | Not verified / not observed |
|---|---|---|
| **National Scholarship Portal** (official) | Scheme listing with "specification, FAQ and scheme opening and closing timeline"; a "Scholarship Eligibility" page "to know your eligibility for different scholarship schemes"; announcements; One Time Registration and applications ([NSP Students page](https://scholarships.gov.in/Students)). | How the eligibility page works: it returned no content to a non-browser client. No public change history, field-level evidence or freshness indicators were observed on the listing. |
| **Buddy4Study** (aggregator) | Profile-based matching and alerts/updates to a large user base, described as AI matching ([WhatsApp Business case study](https://business.whatsapp.com/resources/success-stories/buddy4study)); listing pages offer a follow option promising alerts on deadline-extension updates (observed in search snippets of buddy4study.com listing pages). | Matching method, whether eligibility uses abstention, and whether sources/evidence are shown: the homepage content could not be retrieved for inspection. |
| **Rule/expert systems for scholarships** | Rule-based eligibility checking for university scholarships ([Engin et al., 2014, Procedia CS 31](https://research.sabanciuniv.edu/24349)). | Explanation and freshness handling not described in the abstract. |
| **ML scholarship classifiers** | SVM / random-forest eligibility classification on historical applicant data (e.g. [UST Yemen repository](https://repository.ust.edu.ye/handle/123456789/1536)). | Work on static data; not explainable per rule. |
| **Three-level eligibility demos** | GO / MAYBE / NO-GO eligibility with reasons and missing information ([FundFlow AI, hackathon project](https://lablab.ai/ai-hackathons/nativebuilder-build-without-limits/eterniti/fundflow-ai-scholarship-funding-intelligence)). | Not peer reviewed; no source monitoring described. |
| **Knowledge-based recommenders** | Constraint-based recommendation is a mature area (survey: [Graz/Frontiers 2024](https://graz.elsevierpure.com/en/publications/knowledge-based-recommender-systems-overview-and-research-directi)). | — |
| **Web change detection** | Separating content from layout changes: Vi-DIFF ([HAL](https://hal.archives-ouvertes.fr/hal-01292022)), WebEvo ([ISSTA 2021](https://conf.researchr.org/details/issta-2021/issta-2021-technical-papers/6/WebEvo-Taming-Web-Application-Evolution-via-Detecting-Semantic-Structure-Changes)); commercial monitors filter cosmetic noise. | — |
| **Truth discovery / data fusion** | Resolving conflicting source values and source quality: Latent Truth Model ([Zhao et al., VLDB 2012](https://arxiv.org/pdf/1203.0058)); knowledge fusion ([Dong et al.](https://arxiv.org/pdf/1503.00302)). | — |

## 3. The gap selected

None of the systems above that we could inspect **publicly documents** the combination of:

1. **field-level provenance** shown to the student (value, quoted source text, method, retrieval time),
2. a **retained change history** of eligibility-relevant fields with material vs. cosmetic classification,
3. **three-valued eligibility** that separates "you must provide X", "you must confirm Y" and "the record itself does
   not state Z", each linked to evidence, and
4. a **measured comparison** of static versus monitored data on the same day's official ground truth.

Each element exists separately in prior work (eligibility pages, alerts, three-level labels, change detection,
truth discovery). The gap is their integration for scholarships, plus measurement. This is a gap claim about what is
*publicly documented*, not a claim that no system does it.

## 4. Proposed contribution

An end-to-end, auditable pipeline (registered sources → safe fetch → deterministic parse → entity resolution →
field observations with evidence → policy-based change acceptance with versioning → trust and freshness statuses →
three-valued explainable eligibility), with AI confined to quote-verified extraction that always goes to human
review, and a reproducible evaluation harness with baselines.

## 5. What is implemented and tested

Everything in the README "What works" table: 100 offline backend tests, 5 live smoke tests against real sources,
a frontend type-check/build/lint, and a Playwright end-to-end run of the full demonstration scenario. Two live NSP
checks ran on the real site; the scheduler runs in-process.

## 6–7. Experimental evidence, baselines and measured results

| Claim | Evidence | Baseline |
|---|---|---|
| Monitoring fixes stale data that matters to students | E5: deadline correct for 28/28 records after one check vs 23/28 static; 0 vs 4 of 19 actionable persona matches hidden as "closed" | static dataset dates |
| Cosmetic noise is filtered without missing material changes | E3: 7/7 labelled field changes found, 0/3 cosmetic revisions alerted; page monitor precision 1.00 | byte hash: 3/3 cosmetic false alarms, precision 0.60 / 0.33 |
| Uncertain matches are not merged | E2: 0 wrong merges, 1 deferred to review, recall 0.96 | name similarity alone: same result on this data (no measured advantage) |
| Three-valued logic reduces false hope | E4: false-positive eligibility 0.00 vs 0.86 (v1 engine) and 0.33 (unknown-as-satisfied ablation) | original v1 engine; ablation |
| AI extraction can be constrained to verifiable values, but not fully | E6: 20/21 correct over 3 archived runs; 1 misattributed value (a parent's disability read as the student's) passed validation | none (no unvalidated extractor was scored) |

## Limitations

- **Labels:** all gold labels were created by the developer (an AI assistant) and not yet checked by a human. E4's
  perfect score partly reflects shared interpretation between rule author and labeller.
- **Scale:** 31 catalogue records, 6 registered sources (5 enabled), one NSP snapshot date, 2 scored LLM documents.
- **Coverage:** no state portals; the Reliance portal is JavaScript-rendered and disabled (no browser rendering);
  no OCR for scanned PDFs.
- **Ranking quality:** no student relevance judgements, so no Precision@K / Recall@K.
- **Latency:** change-detection latency is not measurable without knowing when sources changed.
- **Normalisation:** some dataset fields are interpreted by configurable rules (e.g. "Higher Education" ⇒ UG/PG).
  These interpretations are documented but may be wrong for individual schemes.
- **Security:** localStorage JWT, per-process rate limiting, no 2FA (see [SECURITY.md](SECURITY.md)).

## Future work

Human re-labelling with agreement statistics; a second and third NSP snapshot over time; state scholarship portals;
browser rendering for permitted JavaScript sites; OCR; email notifications for saved scholarships; student relevance
feedback for ranking evaluation; probabilistic truth discovery once multiple official sources overlap.

## 9. "What is new in your project?"

> Not the stack and not the use of an LLM. What is new is that every eligibility statement we show a student can be
> traced to the exact source sentence, retrieval time and method that supports it; when a source changes we keep the
> old value and classify the change; and the engine refuses to call a student eligible when information is missing,
> telling them precisely whether *they* or *the record* is missing it. We measured why this matters: on 18 October
> 2026, the static dataset showed 5 open NSP schemes as closed; one monitored check fixed all of them, and our
> three-valued logic cut false "eligible" results from 86% (original engine) to 0% on our labelled cases.

## 10. "How is it different from existing portals?"

> NSP is the authority for its own schemes and lists their windows, but we did not observe change history, evidence
> or per-rule explanations on its public listing, and it covers only NSP-hosted schemes. Buddy4Study aggregates and
> matches across providers and sends alerts, but its public pages do not document how matching works or where each
> fact comes from. ScholarScope sits between them: it monitors official sources (NSP and scheme owners), shows
> evidence and history per field, and explains eligibility rule by rule with explicit uncertainty. It is far
> smaller than either and does not replace applying on the official portal.

## 11. Likely faculty objections and responses

1. **"This is just a scraper with a UI."** Scraping is one module. The contribution is what happens after retrieval:
   entity resolution that refuses uncertain merges (E2: 0 wrong merges), material/cosmetic change classification
   with versioning (E3), field-level provenance, and conservative eligibility (E4). Failed checks are recorded, never
   hidden (demo step 12).
2. **"Your evaluation labels are your own; the 100% scores are meaningless."** Agreed that they are preliminary; the
   report says so on every page. The comparative results are more robust than the absolute ones: the v1 engine's
   86% false-eligible rate and the 5 wrongly closed NSP schemes do not depend on fine labelling choices, and the
   ground truth for E5 is the official listing itself. Human re-labelling is the first item of future work.
3. **"Is scraping government sites legal or ethical?"** Only public pages are fetched, robots.txt is honoured, requests
   are rate-limited with an identifiable user agent, and 401/403 responses pause the source instead of triggering any
   bypass. NSP publishes no robots.txt restrictions (404) and offers no API, so we checked one listing page every 6 h.
4. **"Why use an LLM at all, and how do you stop hallucinations?"** Deadlines and decisions never depend on the LLM. It
   only proposes fields from unstructured guidelines; each value must carry a verbatim quote found in the document,
   pass context and range checks and an injection check, and then an admin approves it. E6 shows why the admin step is
   needed: 20/21 fields were correct, but one misattributed value passed every automatic check.
   With no key, the system still works and says extraction is unavailable.
5. **"Three-valued logic just means you answer 'maybe' to everything."** On 38 labelled cases only the 12 genuinely
   undecidable ones were "maybe"; all 24 not-eligible cases were still excluded with the failing rule named. Each
   "maybe" names the single missing item, and answering it resolves the result (tested in `test_api.py`). Telling a
   student "maybe, if you confirm X" is more useful and more honest than a false "yes".

## Sources

- NSP Students page: https://scholarships.gov.in/Students
- NSP All Scholarships listing (archived copy in `evaluation/snapshots/`): https://scholarships.gov.in/All-Scholarships
- Buddy4Study (WhatsApp Business case study): https://business.whatsapp.com/resources/success-stories/buddy4study
- Engin et al. 2014, rule-based expert systems for supporting university students: https://research.sabanciuniv.edu/24349
- SVM scholarship decisions (UST Yemen): https://repository.ust.edu.ye/handle/123456789/1536
- FundFlow AI (hackathon): https://lablab.ai/ai-hackathons/nativebuilder-build-without-limits/eterniti/fundflow-ai-scholarship-funding-intelligence
- Knowledge-based recommender systems survey: https://graz.elsevierpure.com/en/publications/knowledge-based-recommender-systems-overview-and-research-directi
- Vi-DIFF: https://hal.archives-ouvertes.fr/hal-01292022
- WebEvo (ISSTA 2021): https://conf.researchr.org/details/issta-2021/issta-2021-technical-papers/6/WebEvo-Taming-Web-Application-Evolution-via-Detecting-Semantic-Structure-Changes
- Latent Truth Model (Zhao et al.): https://arxiv.org/pdf/1203.0058
- From Data Fusion to Knowledge Fusion (Dong et al.): https://arxiv.org/pdf/1503.00302

> **Paper:** an 8-page IEEE-style manuscript, its research dossier and audits are in [paper/](paper/) (`main.tex`, `main.pdf`, `RESEARCH_DOSSIER.md`, `AUDIT_AND_REVIEW.md`). Results there supersede any earlier figures in these docs.
