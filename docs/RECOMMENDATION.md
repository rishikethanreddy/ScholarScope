# Eligibility and recommendation algorithm

Code: `app/services/recommendation/` (`eligibility.py`, `scoring.py`, `engine.py`). The pipeline is:

**A. hard constraints → B. unresolved information → C. soft relevance → D. availability → E. explanation**

## A–B. Three-valued criteria

Each criterion returns `satisfied`, `not_satisfied`, `unknown` or `not_applicable`. `unknown` always carries a reason:

| Reason | Meaning | How it is resolved |
|---|---|---|
| `student_missing` | profile lacks a value the rule needs | link to the exact profile field |
| `needs_confirmation` | scheme-specific condition (e.g. "maximum two girls per family", "admission to a notified institution", lateral entry, open-ended course lists, percentile thresholds, alternative routes) | yes / no / not sure question; answer stored per scholarship and marked self-declared |
| `scholarship_unresolved` | the record does not state the rule in structured form | needs source verification, not student input |

Criteria: education level; class range (school students); year of study (post-school); discipline (strict/open);
academic threshold (percentage or CGPA, **no automatic CGPA↔percentage conversion**, different CGPA scales ⇒
question); family income (inclusive ceiling); gender; category (with alternative beneficiary tags such as PM CARES);
disability (+ minimum percentage); state; beneficiary groups (OR within the group); citizenship; scheme questions.

### Outcome

| Condition | Outcome | Label shown |
|---|---|---|
| any `not_satisfied` | `not_eligible` | Not eligible based on recorded criteria (the failing rule is shown) |
| any `unknown` from the student side | `potential_match` | Potential match; more information needed |
| only scholarship-side `unknown` | `eligible_pending_verification` | Meets recorded criteria; some rules need source verification |
| everything satisfied / not applicable | `eligible` | Eligible based on recorded criteria |

Unknown is **never** treated as satisfied. The UI and every explanation state that this is not an official decision.

## C. Relevance score (separate from eligibility)

Computed only for records that are not `not_eligible`. Weights in `config/scoring_config.json`; each factor ∈ [0,1];
score = 100 × Σ wᵢfᵢ / Σ wᵢ.

| Factor | Weight | Definition |
|---|---|---|
| targeting | 0.30 | 0.25 + 0.25 per signal (names your discipline, single target level, targets your group/category, restricted to your state, targets your gender/disability), capped at 1 |
| academic_margin | 0.20 | 0.5 + (your % − minimum)/(100 − minimum), clipped; CGPA analogous; 0.5 when no comparable threshold |
| financial_need_fit | 0.20 | 1 − 0.7 × (income / ceiling); 0.5 when no ceiling |
| benefit_size | 0.15 | log₁₀(1+max amount) / log₁₀(1+₹2 lakh), clipped; 0.5 when not numeric |
| criteria_certainty | 0.15 | satisfied / applicable criteria |

The score is a **ranking aid, not a probability of selection**. Each factor's value, weight, contribution and a
plain-language detail are returned and shown in the UI.

## D. Availability

Computed from dates on the request day: `upcoming` (before open date), `open`, `closed` (after deadline, or an
official closure statement accepted in review), `unknown` (no deadline). `deadline_approaching` when ≤14 days remain.

## Ranking

outcome tier (eligible → pending verification → potential → not eligible) → availability (open → upcoming → unknown →
closed) → relevance score.

## E. Explanations and evidence

Every criterion explanation is generated from the evaluated values ("Your family income ₹3,00,000 is within the
₹8,00,000 ceiling") and carries the highest-precedence current evidence for the rule's field (source, snippet,
method, retrieval time, verification status).

## "New opportunities for me"

On the first visit a compact snapshot (outcome, availability, deadline per record) is stored. Later, the dashboard
lists records that are newly published and not excluded, or whose outcome/availability/deadline changed, until the
student clicks **Mark as seen**, which stores a new baseline.

## Evaluating recommendation quality

`python -m evaluation.run` runs E4 (eligibility vs. labelled cases, vs. the v1 engine and an "unknown = satisfied"
ablation) and E5 (effect of fresh data on availability). Precision@K/Recall@K are **not** reported: there are no
student relevance judgements yet. Collecting them is listed as future work.
