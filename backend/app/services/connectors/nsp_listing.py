"""Parser for the National Scholarship Portal public scheme listing (https://scholarships.gov.in/All-Scholarships).

Observed structure (verified 2026-10-18): one Bootstrap accordion item per ministry/department; each scheme is a
`div.row.mb-4.border-1.border-bottom` containing an <h6> scheme name, pill <span>s such as
"Scheme Open from : 01-06-2026" / "Student Application Open till : 31-10-2026" (optionally "(for Renewal)"),
and links "Specifications" (guideline PDF) and "FAQ".

The parser is deterministic and versioned. It never infers values that are not printed on the page.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.services.normalize import clean, parse_date

PARSER_VERSION = "nsp-listing/1.0"

_SUFFIX = re.compile(r"\s*\(((?:merit|welfare|need)[^)]*?)\s*scheme\)\s*$", re.I)
_PILL = re.compile(r"^(?P<label>.+?)\s*(?P<renewal>\(for renewal\))?\s*:\s*(?P<date>\d{1,2}-\d{1,2}-\d{4})\s*$", re.I)


@dataclass
class NspScheme:
    name: str
    title: str  # name without the "(Merit Based Scheme)" suffix
    scheme_type: Optional[str]
    ministry: Optional[str]
    open_date: Optional[date]
    deadline: Optional[date]
    renewal_only: bool
    other_dates: dict[str, str] = field(default_factory=dict)
    guideline_url: Optional[str] = None
    faq_url: Optional[str] = None
    snippet: str = ""
    location: str = ""
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["open_date"] = self.open_date.isoformat() if self.open_date else None
        d["deadline"] = self.deadline.isoformat() if self.deadline else None
        return d


def parse_nsp_listing(html: str, base_url: str = "https://scholarships.gov.in/") -> list[NspScheme]:
    soup = BeautifulSoup(html, "html.parser")
    ministries: dict[str, str] = {}
    for btn in soup.select("button.accordion-button"):
        target = (btn.get("data-bs-target") or "").lstrip("#")
        if target:
            ministries[target] = clean(btn.get_text(" "))

    schemes: list[NspScheme] = []
    for idx, row in enumerate(soup.select("div.row.mb-4.border-1.border-bottom")):
        h6 = row.find("h6")
        if not h6:
            continue
        name = clean(h6.get_text(" ")).replace("�", "-")
        if not name:
            continue
        parent = row.find_parent(attrs={"id": re.compile(r"^collapse")})
        ministry = ministries.get(parent.get("id")) if parent else None

        m = _SUFFIX.search(name)
        title = _SUFFIX.sub("", name).strip() if m else name
        scheme_type = m.group(1).strip().title() if m else None

        open_date = deadline = None
        renewal_flags: list[bool] = []
        other: dict[str, str] = {}
        warnings: list[str] = []
        for span in row.select("span"):
            text = clean(span.get_text(" "))
            pm = _PILL.match(text)
            if not pm:
                if text:
                    warnings.append(f"Unparsed label: {text}")
                continue
            label = re.sub(r"\s+", " ", pm.group("label")).strip().lower()
            parsed = parse_date(pm.group("date"))
            if parsed is None:
                warnings.append(f"Unparseable date in: {text}")
                continue
            if label.startswith("scheme open from"):
                open_date = parsed
                renewal_flags.append(bool(pm.group("renewal")))
            elif label.startswith("student application open till"):
                deadline = parsed
                renewal_flags.append(bool(pm.group("renewal")))
            else:
                other[label] = parsed.isoformat()

        guideline = faq = None
        for a in row.find_all("a", href=True):
            label = clean(a.get_text(" ")).lower()
            href = urljoin(base_url, a["href"].strip())
            if label.startswith("specification") or label.startswith("guideline"):
                guideline = None if href.endswith("not_available.pdf") else href
            elif label == "faq":
                faq = None if href.endswith("not_available.pdf") else href

        if deadline is None:
            warnings.append("No student application deadline printed")
        schemes.append(NspScheme(
            name=name, title=title, scheme_type=scheme_type, ministry=ministry, open_date=open_date,
            deadline=deadline, renewal_only=bool(renewal_flags) and all(renewal_flags), other_dates=other,
            guideline_url=guideline, faq_url=faq, snippet=" | ".join(clean(t) for t in row.stripped_strings if clean(t))[:600],
            location=f"{ministry or 'Featured'} › row {idx}", warnings=warnings,
        ))
    return _dedupe(schemes)


def _dedupe(schemes: list[NspScheme]) -> list[NspScheme]:
    """The page repeats featured schemes above the accordion. Keep the ministry-section row."""
    by_title: dict[str, NspScheme] = {}
    for s in sorted(schemes, key=lambda x: x.ministry is None):
        key = s.title.lower()
        kept = by_title.get(key)
        if kept is None:
            by_title[key] = s
            continue
        if s.guideline_url != kept.guideline_url or s.deadline != kept.deadline:
            kept.warnings.append(
                f"Duplicate listing ({s.location}) shows guideline={s.guideline_url}, deadline={s.deadline}"
            )
    order = {id(s): i for i, s in enumerate(schemes)}
    return sorted(by_title.values(), key=lambda s: order[id(s)])
