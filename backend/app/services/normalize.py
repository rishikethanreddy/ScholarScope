"""Normalization of free-text scholarship attributes into the structured schema.

All interpretation rules come from config/vocabulary.json. Every function returns a value plus,
where interpretation was needed, a human-readable issue so the import report can show it.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Optional

from app.core.config import load_config_file


def vocab() -> dict:
    return load_config_file("vocabulary.json")


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def is_unknown(value: Any) -> bool:
    return clean(value).lower() in vocab()["unknown_values"]


# --------------------------------------------------------------------------- names


_SCHEME_SUFFIX = re.compile(r"\((merit|welfare|need)[^)]*scheme\)\s*$", re.I)
_PUNCT = re.compile(r"[^a-z0-9 ]+")
_ABBREV = {"&": " and ", "–": " ", "—": " ", "-": " "}


def normalize_name(name: str) -> str:
    """Lower-case, strip scheme-type suffix and punctuation; keeps discriminating words."""
    text = clean(name)
    text = _SCHEME_SUFFIX.sub("", text)
    for a, b in _ABBREV.items():
        text = text.replace(a, b)
    text = text.lower().replace("�", " ")
    text = _PUNCT.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------- dates / numbers

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%d %B, %Y")


def parse_date(value: Any) -> Optional[date]:
    """Parse an unambiguous date. Returns None for unknown or ambiguous input (never guesses)."""
    text = clean(value)
    if not text or is_unknown(text):
        return None
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text, flags=re.I)
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        if 2000 <= parsed.year <= 2100:
            return parsed
    return None


def parse_number(value: Any) -> Optional[float]:
    text = clean(value).replace(",", "")
    if not text or is_unknown(text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_amount_max(text: str) -> Optional[float]:
    """Best-effort maximum INR amount for display/sorting only. None when the text is not numeric enough."""
    t = clean(text).replace(",", "")
    if not t or is_unknown(t):
        return None
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", t)]
    numbers = [n for n in numbers if n >= 100]  # drop list markers like "4th"
    return max(numbers) if numbers else None


def split_list(text: str) -> list[str]:
    t = clean(text)
    if not t or is_unknown(t):
        return []
    parts = re.split(r";|\n|,(?![^()]*\))", t)
    return [p.strip(" .") for p in parts if p.strip(" .")]


# --------------------------------------------------------------------------- education

_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}


def _class_num(token: str) -> Optional[int]:
    token = token.lower().strip()
    if token.isdigit():
        return int(token)
    return _ROMAN.get(token)


def parse_class_range(*texts: str) -> Optional[list[int]]:
    """'Class I-X' -> [1, 10]; 'Class 9-12' -> [9, 12]; 'IX-X' -> [9, 10]; 'Standard VIII ...' -> [8, 12]."""
    for text in texts:
        t = clean(text)
        m = re.search(r"(?:class|std|standard)?\s*\b([ivx]+|\d{1,2})\s*[-–]\s*([ivx]+|\d{1,2})\b", t, re.I)
        if m and (re.search(r"class|std|standard", t, re.I) or re.fullmatch(r"[ivx]+\s*[-–]\s*[ivx]+", t, re.I)):
            lo, hi = _class_num(m.group(1)), _class_num(m.group(2))
            if lo and hi and 1 <= lo <= hi <= 12:
                return [lo, hi]
        m = re.search(r"(?:standard|class)\s+([ivx]+|\d{1,2})\b.*(?:through|to|up to)", t, re.I)
        if m and _class_num(m.group(1)):
            return [_class_num(m.group(1)), 12]
    return None


def parse_allowed_years(text: str) -> Optional[list[int]]:
    """'1st year' -> [1]; '1st-4th year' -> [1,2,3,4]; '1st year or 2nd year through lateral entry' -> [1,2]."""
    t = clean(text).lower()
    m = re.fullmatch(r"(\d)(?:st|nd|rd|th)\s*[-–]\s*(\d)(?:st|nd|rd|th)\s+year", t)
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    m = re.fullmatch(r"(\d)(?:st|nd|rd|th) year(?: or (\d)(?:st|nd|rd|th) year.*)?", t)
    if m:
        years = [int(m.group(1))]
        if m.group(2):
            years.append(int(m.group(2)))
        return years
    return None


def map_education(level_text: str) -> tuple[str, list[str], Optional[str]]:
    key = clean(level_text).lower()
    mapping = vocab()["education_level_map"]
    note = vocab().get("education_level_notes", {}).get(key)
    if key not in mapping:
        return "unknown", [], f"Unmapped education level '{level_text}'"
    levels = mapping[key]
    if levels == "unknown":
        return "unknown", [], note
    return "levels", list(levels), note


def map_disciplines(fields_text: str) -> tuple[str, list[str], Optional[str]]:
    t = clean(fields_text).lower()
    if not t or is_unknown(t):
        return "unknown", [], "Course/discipline eligibility not recorded"
    for rule in vocab()["discipline_map"]:
        if re.search(rule["pattern"], t, re.I):
            return rule["rule"], list(rule["disciplines"]), None
    return "unknown", [], f"Unmapped discipline text '{fields_text}'"


# --------------------------------------------------------------------------- demographics


def map_categories(text: str) -> tuple[list[str], list[str], Optional[str]]:
    t = clean(text)
    low = t.lower()
    v = vocab()
    if not t or any(re.search(p, low) for p in v["category_no_restriction_patterns"]):
        note = t if t and low not in ("any", "all") else None
        return [], [], note
    codes = {c["code"] for c in v["categories"]}
    found = [tok for tok in re.split(r"[/,;]| or ", t.upper().replace(" ", "")) if tok in codes]
    alt = [p["tag"] for p in v["category_alt_tag_patterns"] if re.search(p["pattern"], low)]
    if not found and not alt:
        return [], [], f"Unstructured category rule: {t}"
    return found, alt, None


def map_genders(text: str) -> list[str]:
    t = clean(text).lower()
    if t in ("", "any", "all"):
        return []
    if t in ("female", "girls", "women", "girl"):
        return ["FEMALE"]
    if t in ("male", "boys", "men"):
        return ["MALE"]
    return []


def map_disability(text: str) -> tuple[str, Optional[float]]:
    t = clean(text)
    if t.lower() in ("", "any", "no", "none"):
        return "none", None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", t)
    return "required", float(m.group(1)) if m else None


def canonical_state(name: str) -> Optional[str]:
    v = vocab()
    t = clean(name).lower()
    if t in v["state_aliases"]:
        return v["state_aliases"][t]
    for s in v["states"]:
        if s.lower() == t:
            return s
    return None


def map_states(text: str) -> tuple[list[str], Optional[str]]:
    t = clean(text)
    if not t or any(re.search(p, t.lower()) for p in vocab()["all_india_patterns"]):
        return [], None
    states, unknown = [], []
    for part in re.split(r";|,", t):
        if not part.strip():
            continue
        c = canonical_state(part)
        (states if c else unknown).append(c or part.strip())
    note = f"Unrecognised state names: {', '.join(unknown)}" if unknown else None
    return states, note


def condition_key(text: str) -> str:
    return "q:" + hashlib.sha1(normalize_name(text).encode()).hexdigest()[:10]


def map_conditions(text: str) -> list[dict]:
    """Turn special_background_requirement text into structured conditions (see vocabulary.json)."""
    t = clean(text)
    if not t or is_unknown(t) or t.lower() in ("any", "none"):
        return []
    tags: list[str] = []
    tag_texts: list[str] = []
    conditions: list[dict] = []
    citizenship = False
    for segment in [s.strip() for s in t.split(";") if s.strip()]:
        matched = False
        for rule in vocab()["condition_patterns"]:
            if not re.search(rule["pattern"], segment, re.I):
                continue
            matched = True
            if "tags" in rule:
                tags.extend(x for x in rule["tags"] if x not in tags)
                tag_texts.append(segment)
            if rule.get("citizenship"):
                citizenship = True
        if not matched:
            conditions.append({"key": condition_key(segment), "kind": "question", "text": segment})
    if tags:
        conditions.insert(0, {"key": "tags:beneficiary", "kind": "profile_tags", "tags": tags, "text": "; ".join(tag_texts)})
    if citizenship:
        conditions.insert(0, {"key": "citizenship", "kind": "citizenship", "text": "Indian national / resident"})
    return conditions


# --------------------------------------------------------------------------- academic / income


def map_academic(value: str, details: str) -> dict:
    """Interpret minimum_cgpa_or_percentage together with minimum_marks_details."""
    v = vocab()
    raw, det = clean(value), clean(details)
    low_det = det.lower()
    result = {
        "academic_rule": "unknown",
        "min_percentage": None,
        "min_cgpa": None,
        "cgpa_scale": 10.0,
        "academic_has_alternative": bool(re.search(v["academic_alternative_pattern"], low_det)),
        "academic_note": det or None,
    }
    number = parse_number(raw)
    if number is not None and re.search(v["academic_percentile_pattern"], low_det):
        result["academic_rule"] = "percentile"
        result["min_percentage"] = None
        return result
    if number is not None:
        if number <= 10:
            result.update(academic_rule="cgpa", min_cgpa=number)
        elif number <= 100:
            result.update(academic_rule="percentage", min_percentage=number)
        return result
    if any(p in low_det for p in v["academic_none_patterns"]):
        result["academic_rule"] = "none"
    return result


def income_amounts_in_text(text: str) -> list[float]:
    """Rupee amounts stated in prose: '₹2.5 lakh' -> 250000, '₹800,000' -> 800000."""
    t = clean(text).lower().replace(",", "")
    amounts = [float(n) * 100000 for n in re.findall(r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)\s*lakh", t)]
    amounts += [float(n) for n in re.findall(r"(?:₹|rs\.?|inr)\s*(\d{4,})(?!\s*lakh|\d)", t)]
    return amounts


def map_income(value: str, details: str) -> dict:
    raw = clean(value)
    number = parse_number(raw)
    if number is not None and number > 0:
        stated = income_amounts_in_text(details)
        if stated and all(abs(s - number) > 0.01 * number for s in stated):
            return {
                "income_rule": "unknown",
                "income_limit": None,
                "income_note": f"CONFLICT: numeric value {number:,.0f} disagrees with details text "
                f"'{clean(details)}'. Needs source verification.",
            }
        return {"income_rule": "limit", "income_limit": number, "income_note": clean(details) or None}
    if raw.lower() in vocab()["income_none_values"]:
        return {"income_rule": "none", "income_limit": None, "income_note": clean(details) or None}
    return {"income_rule": "unknown", "income_limit": None, "income_note": clean(details) or None}


def map_provider_type(text: str) -> str:
    t = clean(text).lower()
    if "government" in t:
        return "government"
    if "foundation" in t or "trust" in t:
        return "private_foundation"
    if "corporate" in t or "company" in t:
        return "corporate"
    if "university" in t or "institut" in t:
        return "institution"
    return "other"


def map_scholarship_type(text: str) -> str:
    t = clean(text).lower()
    if "cum" in t:
        return "merit_cum_means"
    if "merit" in t:
        return "merit"
    if "need" in t or "means" in t:
        return "need"
    if "welfare" in t:
        return "welfare"
    return "other"


def map_renewal(status_text: str, *, explicit_renewal: Optional[bool] = None) -> str:
    if explicit_renewal is True:
        return "renewal"
    t = clean(status_text).lower()
    if "renewal" in t:
        return "renewal"
    return "unknown"


# --------------------------------------------------------------------------- dataset row


def normalize_dataset_row(row: dict[str, str]) -> tuple[dict, list[str]]:
    """Map one row of the researched CSV schema to scholarship fields. Returns (fields, issues)."""
    issues: list[str] = []
    g = lambda k: clean(row.get(k, ""))  # noqa: E731

    edu_rule, levels, edu_note = map_education(g("education_level"))
    if edu_note and edu_rule == "unknown":
        issues.append(edu_note)
    disc_rule, disciplines, disc_note = map_disciplines(g("eligible_fields"))
    if disc_note and disc_rule == "unknown":
        issues.append(disc_note)
    cats, alt_tags, cat_note = map_categories(g("category"))
    states, state_note = map_states(g("eligible_states"))
    if state_note:
        issues.append(state_note)
    dis_rule, dis_pct = map_disability(g("disability_requirement"))
    academic = map_academic(g("minimum_cgpa_or_percentage"), g("minimum_marks_details"))
    if academic["academic_rule"] == "unknown":
        issues.append("Academic threshold not recorded in structured form")
    if academic["academic_rule"] == "percentile":
        issues.append("Academic threshold is a percentile, not a percentage; stored as a question")
    income = map_income(g("maximum_family_income"), g("income_criteria_details"))
    if income["income_note"] and income["income_note"].startswith("CONFLICT"):
        issues.append(income["income_note"])
    elif income["income_rule"] == "unknown":
        issues.append("Income ceiling unknown")
    conditions = map_conditions(g("special_background_requirement"))
    if academic["academic_rule"] == "percentile":
        conditions.append(
            {
                "key": condition_key("academic percentile " + g("minimum_marks_details")),
                "kind": "question",
                "text": g("minimum_marks_details"),
            }
        )

    open_date = parse_date(g("application_start_date"))
    deadline = parse_date(g("application_deadline"))
    if g("application_deadline") and not deadline:
        issues.append(f"Deadline not parseable/unknown: '{g('application_deadline')}'")
    if open_date and deadline and open_date > deadline:
        issues.append("Opening date is after deadline")

    name = g("scholarship_name")
    fields = {
        "external_id": g("scholarship_id") or None,
        "name": name,
        "normalized_name": normalize_name(name),
        "provider": g("provider") or None,
        "provider_type": map_provider_type(g("provider_type")),
        "scholarship_type": map_scholarship_type(g("scholarship_type")),
        "education_rule": edu_rule,
        "education_levels": levels,
        "class_range": parse_class_range(g("year_of_study"), g("eligible_courses")),
        "allowed_years": parse_allowed_years(g("year_of_study")),
        "courses_text": g("eligible_courses") or None,
        "fields_text": g("eligible_fields") or None,
        "year_of_study_text": g("year_of_study") or None,
        "discipline_rule": disc_rule,
        "disciplines": disciplines,
        **academic,
        **income,
        "income_currency": "INR",
        "genders": map_genders(g("gender")),
        "categories": cats,
        "category_alt_tags": alt_tags,
        "category_note": cat_note,
        "disability_rule": dis_rule,
        "min_disability_percent": dis_pct,
        "eligible_states": states,
        "domicile_note": None if is_unknown(g("domicile_requirement")) else g("domicile_requirement"),
        "conditions": conditions,
        "special_note": g("special_background_requirement") or None,
        "age_note": None if is_unknown(g("age_requirement")) else g("age_requirement"),
        "exclusions": g("combination_restrictions") or None,
        "amount_text": None if is_unknown(g("scholarship_amount")) else g("scholarship_amount"),
        "amount_max_inr": parse_amount_max(g("scholarship_amount")),
        "amount_frequency": None if is_unknown(g("amount_frequency")) else g("amount_frequency"),
        "required_documents": split_list(g("required_documents")),
        "open_date": open_date,
        "deadline": deadline,
        "renewal_type": map_renewal(g("application_status")),
        "status_reported": g("application_status") or None,
        "application_method": g("application_method") or None,
        "application_url": g("official_application_url") or None,
        "official_source_url": g("official_source_url") or None,
        "description": g("short_description") or None,
        "eligibility_summary": g("eligibility_summary") or None,
        "selection_process": g("selection_process") or None,
        "academic_year": "2026-27" if "2026" in g("application_start_date") + g("application_deadline") else None,
    }
    if not name:
        issues.append("REJECT: missing scholarship_name")
    for url_field in ("application_url", "official_source_url"):
        url = fields[url_field]
        if url and not re.match(r"^https?://", url):
            issues.append(f"{url_field} is not an http(s) URL")
            fields[url_field] = None
    return fields, issues
