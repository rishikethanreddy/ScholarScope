"""Soft relevance scoring, kept separate from hard eligibility.

Factors (each 0..1, weights in config/scoring_config.json):
  targeting           How specifically the scheme targets this student (named discipline, single level,
                      declared beneficiary group, restricted state) versus being open to everyone.
  academic_margin     How far the student is above a stated academic threshold (neutral when none applies).
  financial_need_fit  For schemes with an income ceiling: lower income relative to the ceiling scores higher.
  benefit_size        Log-scaled maximum stated amount relative to a reference amount (neutral if unknown).
  criteria_certainty  Share of applicable criteria that are definitely satisfied (fewer unknowns ranks higher).
"""
from __future__ import annotations

import math
from typing import Any

from app.core.config import load_config_file
from app.services.recommendation.eligibility import NA, SATISFIED, UNKNOWN


def _cfg() -> dict:
    return load_config_file("scoring_config.json")


def score(student: Any, s: Any, criteria: list[dict]) -> dict:
    cfg = _cfg()
    w, neutral = cfg["weights"], cfg["neutral_value"]
    by_key = {c["key"]: c for c in criteria}
    factors: dict[str, dict] = {}

    # targeting
    signals = []
    if s.discipline_rule in ("strict", "open") and by_key.get("discipline", {}).get("status") == SATISFIED:
        signals.append("names your discipline")
    if s.education_rule == "levels" and len(s.education_levels) == 1 and by_key.get("education", {}).get("status") == SATISFIED:
        signals.append("targets your education level only")
    if any(c["key"].startswith("tags:") and c["status"] == SATISFIED for c in criteria) or \
            by_key.get("category", {}).get("status") == SATISFIED:
        signals.append("targets a group you belong to")
    if s.eligible_states and by_key.get("state", {}).get("status") == SATISFIED:
        signals.append("restricted to your state/region")
    if by_key.get("gender", {}).get("status") == SATISFIED or by_key.get("disability", {}).get("status") == SATISFIED:
        signals.append("targets your gender or disability status")
    tval = min(1.0, 0.25 + 0.25 * len(signals))
    factors["targeting"] = {"value": tval, "detail": ", ".join(signals) or "open to a broad population"}

    # academic margin
    pct, cg = getattr(student, "qualifying_exam_percentage", None), getattr(student, "cgpa", None)
    if s.academic_rule == "percentage" and pct is not None and s.min_percentage:
        margin = (pct - s.min_percentage) / max(1.0, 100 - s.min_percentage)
        factors["academic_margin"] = {"value": max(0.0, min(1.0, 0.5 + margin)),
                                      "detail": f"{pct:g}% vs {s.min_percentage:g}% minimum"}
    elif s.academic_rule == "cgpa" and cg is not None and s.min_cgpa:
        margin = (cg - s.min_cgpa) / max(0.5, s.cgpa_scale - s.min_cgpa)
        factors["academic_margin"] = {"value": max(0.0, min(1.0, 0.5 + margin)),
                                      "detail": f"CGPA {cg:g} vs {s.min_cgpa:g} minimum"}
    else:
        factors["academic_margin"] = {"value": neutral, "detail": "no comparable academic threshold (neutral)"}

    # financial need fit
    income = getattr(student, "annual_family_income", None)
    if s.income_rule == "limit" and income is not None and s.income_limit:
        ratio = min(1.0, income / s.income_limit)
        factors["financial_need_fit"] = {"value": round(1 - 0.7 * ratio, 4),
                                         "detail": f"income is {ratio:.0%} of the ₹{s.income_limit:,.0f} ceiling"}
    else:
        factors["financial_need_fit"] = {"value": neutral, "detail": "no income ceiling to compare (neutral)"}

    # benefit size
    if s.amount_max_inr:
        ref = cfg["benefit_reference_inr"]
        val = max(0.0, min(1.0, math.log10(1 + s.amount_max_inr) / math.log10(1 + ref)))
        factors["benefit_size"] = {"value": round(val, 4), "detail": f"up to ₹{s.amount_max_inr:,.0f} stated"}
    else:
        factors["benefit_size"] = {"value": neutral, "detail": "amount not stated numerically (neutral)"}

    # criteria certainty
    applicable = [c for c in criteria if c["status"] != NA]
    sat = sum(1 for c in applicable if c["status"] == SATISFIED)
    unk = sum(1 for c in applicable if c["status"] == UNKNOWN)
    factors["criteria_certainty"] = {"value": round(sat / len(applicable), 4) if applicable else neutral,
                                     "detail": f"{sat} satisfied, {unk} unresolved of {len(applicable)} applicable"}

    total_w = sum(w.values())
    for name, f in factors.items():
        f["weight"] = w.get(name, 0)
        f["contribution"] = round(100 * f["weight"] * f["value"] / total_w, 2)
    return {"score": round(sum(f["contribution"] for f in factors.values()), 1), "factors": factors,
            "note": "Relevance score for ranking only; not a probability of selection."}
