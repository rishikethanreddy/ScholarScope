"""Request bodies (validated). Responses are built by app/api/serializers.py."""
from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.normalize import canonical_state, vocab


def _codes(kind: str) -> set[str]:
    return {x["code"] for x in vocab()[kind]}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ------------------------------------------------------------------ auth

class RegisterIn(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", v):
            raise ValueError("Enter a valid email address")
        return v


class LoginIn(Strict):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


# ------------------------------------------------------------------ student

class ProfileIn(Strict):
    display_name: Optional[str] = Field(default=None, max_length=80)
    education_level: Optional[str] = None
    current_class: Optional[int] = Field(default=None, ge=1, le=12)
    year_of_study: Optional[int] = Field(default=None, ge=1, le=7)
    course_name: Optional[str] = Field(default=None, max_length=120)
    discipline: Optional[str] = None
    qualifying_exam_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    cgpa: Optional[float] = Field(default=None, ge=0, le=10)
    cgpa_scale: float = Field(default=10.0, gt=0, le=10)
    annual_family_income: Optional[float] = Field(default=None, ge=0, le=1e9)
    state: Optional[str] = None
    gender: Optional[str] = None
    category: Optional[str] = None
    has_disability: Optional[bool] = None
    disability_percent: Optional[float] = Field(default=None, ge=0, le=100)
    is_indian_citizen: Optional[bool] = None
    special_circumstances: list[str] = Field(default_factory=list, max_length=20)
    special_circumstances_none: bool = False

    @field_validator("education_level")
    @classmethod
    def _level(cls, v):
        if v is not None and v not in _codes("education_levels"):
            raise ValueError("Unknown education level")
        return v

    @field_validator("discipline")
    @classmethod
    def _disc(cls, v):
        if v is not None and v not in _codes("disciplines"):
            raise ValueError("Unknown discipline")
        return v

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v is not None and v not in _codes("categories"):
            raise ValueError("Unknown category")
        return v

    @field_validator("gender")
    @classmethod
    def _gender(cls, v):
        if v is not None and v not in _codes("genders"):
            raise ValueError("Unknown gender value")
        return v

    @field_validator("state")
    @classmethod
    def _state(cls, v):
        if v is None:
            return v
        c = canonical_state(v)
        if not c:
            raise ValueError("Unknown state/UT")
        return c

    @field_validator("special_circumstances")
    @classmethod
    def _tags(cls, v):
        bad = set(v) - _codes("special_circumstances")
        if bad:
            raise ValueError(f"Unknown special circumstances: {sorted(bad)}")
        return sorted(set(v))


class AnswerIn(Strict):
    scholarship_id: str = Field(max_length=36)
    criterion_key: str = Field(max_length=64)
    answer: Literal["yes", "no", "unsure"]


class SavedIn(Strict):
    scholarship_id: str = Field(max_length=36)
    status: Literal["saved", "preparing", "applied", "awarded", "rejected"] = "saved"
    notes: Optional[str] = Field(default=None, max_length=500)


class SavedUpdate(Strict):
    status: Optional[Literal["saved", "preparing", "applied", "awarded", "rejected"]] = None
    notes: Optional[str] = Field(default=None, max_length=500)


# ------------------------------------------------------------------ admin

Classification = Literal["official", "institutional", "aggregator", "other", "fixture"]
ConnectorName = Literal["nsp_listing", "html_page", "pdf_document"]


class SourceIn(Strict):
    key: str = Field(pattern=r"^[a-z0-9_]{3,80}$")
    name: str = Field(min_length=3, max_length=200)
    organization: Optional[str] = Field(default=None, max_length=200)
    classification: Classification
    base_url: str = Field(max_length=1000)
    target_urls: list[str] = Field(min_length=1, max_length=20)
    allowed_url_patterns: list[str] = Field(min_length=1, max_length=20)
    connector: ConnectorName
    connector_config: dict[str, Any] = Field(default_factory=dict)
    crawl_frequency_minutes: int = Field(default=1440, ge=30, le=60 * 24 * 30)
    enabled: bool = True
    priority: int = Field(default=50, ge=0, le=100)
    trust_policy: Optional[str] = Field(default=None, max_length=2000)
    access_notes: Optional[str] = Field(default=None, max_length=2000)
    linked_scholarship_id: Optional[str] = None

    @field_validator("base_url", "target_urls", "allowed_url_patterns")
    @classmethod
    def _urls(cls, v):
        items = v if isinstance(v, list) else [v]
        for u in items:
            if not re.match(r"^(https?|fixture)://", u):
                raise ValueError(f"URL must start with http(s):// (or fixture:// for test fixtures): {u}")
        return v


class SourceUpdate(Strict):
    name: Optional[str] = Field(default=None, min_length=3, max_length=200)
    organization: Optional[str] = Field(default=None, max_length=200)
    classification: Optional[Classification] = None
    target_urls: Optional[list[str]] = Field(default=None, min_length=1, max_length=20)
    allowed_url_patterns: Optional[list[str]] = Field(default=None, min_length=1, max_length=20)
    connector_config: Optional[dict[str, Any]] = None
    crawl_frequency_minutes: Optional[int] = Field(default=None, ge=30, le=60 * 24 * 30)
    enabled: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=0, le=100)
    trust_policy: Optional[str] = Field(default=None, max_length=2000)
    access_notes: Optional[str] = Field(default=None, max_length=2000)
    linked_scholarship_id: Optional[str] = None


class DecisionIn(Strict):
    note: Optional[str] = Field(default=None, max_length=500)


class ApproveIn(Strict):
    payload: Optional[dict[str, Any]] = None
    note: Optional[str] = Field(default=None, max_length=500)


class LinkIn(Strict):
    scholarship_id: str = Field(max_length=36)
