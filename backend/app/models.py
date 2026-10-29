"""Relational schema for ScholarScope AI.

Groups:
  identity      users, student_profiles, student_answers, saved_scholarships, recommendation_snapshots
  catalogue     scholarships, scholarship_versions, field_evidence, scholarship_sources, dataset_versions
  monitoring    sources, crawl_jobs, source_documents
  review        change_events, candidates
  operations    audit_logs
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores UTC; always returns timezone-aware UTC datetimes (SQLite otherwise returns naive values)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


TZDateTime = UTCDateTime()


# --------------------------------------------------------------------------- identity


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="student")  # student | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)

    profile: Mapped[Optional["StudentProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True)


class StudentProfile(Base):
    """Only attributes that an eligibility rule in the catalogue can use. No identity numbers."""

    __tablename__ = "student_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(80))

    # Academic
    education_level: Mapped[Optional[str]] = mapped_column(String(32))  # vocab: education_levels
    current_class: Mapped[Optional[int]] = mapped_column(Integer)  # school students (1-12)
    year_of_study: Mapped[Optional[int]] = mapped_column(Integer)  # year within current programme
    course_name: Mapped[Optional[str]] = mapped_column(String(120))
    discipline: Mapped[Optional[str]] = mapped_column(String(40))  # vocab: disciplines
    qualifying_exam_percentage: Mapped[Optional[float]] = mapped_column(Float)
    cgpa: Mapped[Optional[float]] = mapped_column(Float)
    cgpa_scale: Mapped[float] = mapped_column(Float, default=10.0)

    # Financial / geographic / demographic (all optional; missing ⇒ "unknown", never "satisfied")
    annual_family_income: Mapped[Optional[float]] = mapped_column(Float)
    state: Mapped[Optional[str]] = mapped_column(String(64))
    gender: Mapped[Optional[str]] = mapped_column(String(16))
    category: Mapped[Optional[str]] = mapped_column(String(16))
    has_disability: Mapped[Optional[bool]] = mapped_column(Boolean)
    disability_percent: Mapped[Optional[float]] = mapped_column(Float)
    is_indian_citizen: Mapped[Optional[bool]] = mapped_column(Boolean)
    special_circumstances: Mapped[list] = mapped_column(JSON, default=list)  # vocab tags
    # Explicit statement that none of the special circumstances apply (distinguishes "none" from "not answered")
    special_circumstances_none: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class StudentAnswer(Base):
    """Student's self-declared answer to a scholarship-specific condition (missing-info workflow)."""

    __tablename__ = "student_answers"
    __table_args__ = (UniqueConstraint("profile_id", "scholarship_id", "criterion_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True)
    scholarship_id: Mapped[str] = mapped_column(ForeignKey("scholarships.id", ondelete="CASCADE"))
    criterion_key: Mapped[str] = mapped_column(String(64))
    answer: Mapped[str] = mapped_column(String(8))  # yes | no | unsure
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)


class SavedScholarship(Base):
    __tablename__ = "saved_scholarships"
    __table_args__ = (UniqueConstraint("profile_id", "scholarship_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True)
    scholarship_id: Mapped[str] = mapped_column(ForeignKey("scholarships.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="saved")  # saved|preparing|applied|awarded|rejected
    notes: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    scholarship: Mapped["Scholarship"] = relationship()


class RecommendationSnapshot(Base):
    """Compact record of a student's results, used to show what changed for them since last visit."""

    __tablename__ = "recommendation_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True)
    computed_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    results: Mapped[dict] = mapped_column(JSON)  # {scholarship_id: {outcome, availability, version}}


# --------------------------------------------------------------------------- catalogue


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(64), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    imported_by: Mapped[Optional[str]] = mapped_column(String(36))
    num_rows: Mapped[int] = mapped_column(Integer, default=0)
    num_created: Mapped[int] = mapped_column(Integer, default=0)
    num_updated: Mapped[int] = mapped_column(Integer, default=0)
    num_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    num_rejected: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[dict] = mapped_column(JSON, default=dict)  # per-row issues, quality stats


class Scholarship(Base):
    __tablename__ = "scholarships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    external_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(200))
    provider_type: Mapped[Optional[str]] = mapped_column(String(32))
    scholarship_type: Mapped[Optional[str]] = mapped_column(String(32))

    # Education
    education_rule: Mapped[str] = mapped_column(String(16), default="unknown")  # levels | any | unknown
    education_levels: Mapped[list] = mapped_column(JSON, default=list)
    class_range: Mapped[Optional[list]] = mapped_column(JSON)  # [min_class, max_class] for school schemes
    allowed_years: Mapped[Optional[list]] = mapped_column(JSON)  # e.g. [1] or [1, 2]
    courses_text: Mapped[Optional[str]] = mapped_column(Text)
    fields_text: Mapped[Optional[str]] = mapped_column(Text)
    year_of_study_text: Mapped[Optional[str]] = mapped_column(String(200))
    discipline_rule: Mapped[str] = mapped_column(String(16), default="any")  # any | strict | open | unknown
    disciplines: Mapped[list] = mapped_column(JSON, default=list)

    # Academic
    academic_rule: Mapped[str] = mapped_column(String(16), default="unknown")  # none|percentage|cgpa|percentile|unknown
    min_percentage: Mapped[Optional[float]] = mapped_column(Float)
    min_cgpa: Mapped[Optional[float]] = mapped_column(Float)
    cgpa_scale: Mapped[float] = mapped_column(Float, default=10.0)
    academic_has_alternative: Mapped[bool] = mapped_column(Boolean, default=False)
    academic_note: Mapped[Optional[str]] = mapped_column(Text)

    # Income
    income_rule: Mapped[str] = mapped_column(String(16), default="unknown")  # limit | none | unknown
    income_limit: Mapped[Optional[float]] = mapped_column(Float)
    income_currency: Mapped[str] = mapped_column(String(3), default="INR")
    income_note: Mapped[Optional[str]] = mapped_column(Text)

    # Demographic / geographic
    genders: Mapped[list] = mapped_column(JSON, default=list)  # empty ⇒ any
    categories: Mapped[list] = mapped_column(JSON, default=list)  # empty ⇒ any
    category_alt_tags: Mapped[list] = mapped_column(JSON, default=list)
    category_note: Mapped[Optional[str]] = mapped_column(Text)
    disability_rule: Mapped[str] = mapped_column(String(16), default="none")  # none | required
    min_disability_percent: Mapped[Optional[float]] = mapped_column(Float)
    eligible_states: Mapped[list] = mapped_column(JSON, default=list)  # empty ⇒ all India
    domicile_note: Mapped[Optional[str]] = mapped_column(Text)
    conditions: Mapped[list] = mapped_column(JSON, default=list)  # structured special conditions
    special_note: Mapped[Optional[str]] = mapped_column(Text)
    age_note: Mapped[Optional[str]] = mapped_column(Text)
    exclusions: Mapped[Optional[str]] = mapped_column(Text)

    # Benefit and application
    amount_text: Mapped[Optional[str]] = mapped_column(String(300))
    amount_max_inr: Mapped[Optional[float]] = mapped_column(Float)
    amount_frequency: Mapped[Optional[str]] = mapped_column(String(64))
    required_documents: Mapped[list] = mapped_column(JSON, default=list)
    open_date: Mapped[Optional[date]] = mapped_column(Date)
    deadline: Mapped[Optional[date]] = mapped_column(Date, index=True)
    renewal_type: Mapped[str] = mapped_column(String(16), default="unknown")  # fresh|renewal|both|unknown
    status_reported: Mapped[Optional[str]] = mapped_column(String(32))  # as stated by source/dataset
    application_method: Mapped[Optional[str]] = mapped_column(String(120))
    application_url: Mapped[Optional[str]] = mapped_column(String(1000))
    official_source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    description: Mapped[Optional[str]] = mapped_column(Text)
    eligibility_summary: Mapped[Optional[str]] = mapped_column(Text)
    selection_process: Mapped[Optional[str]] = mapped_column(Text)
    academic_year: Mapped[Optional[str]] = mapped_column(String(16))

    # Freshness / provenance summary (details live in field_evidence and change_events)
    origin: Mapped[str] = mapped_column(String(24), default="dataset_import")  # dataset_import|crawler|manual
    source_published_at: Mapped[Optional[date]] = mapped_column(Date)
    first_discovered_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    verification_status: Mapped[str] = mapped_column(String(32), default="deadline_not_verified")
    verification_flags: Mapped[list] = mapped_column(JSON, default=list)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    dataset_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("dataset_versions.id"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    evidence: Mapped[list["FieldEvidence"]] = relationship(back_populates="scholarship", cascade="all, delete-orphan")
    source_links: Mapped[list["ScholarshipSource"]] = relationship(
        back_populates="scholarship", cascade="all, delete-orphan"
    )


class ScholarshipVersion(Base):
    __tablename__ = "scholarship_versions"
    __table_args__ = (UniqueConstraint("scholarship_id", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scholarship_id: Mapped[str] = mapped_column(ForeignKey("scholarships.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(36))


class FieldEvidence(Base):
    """One observation of one field from one source at one time."""

    __tablename__ = "field_evidence"
    __table_args__ = (Index("ix_evidence_current", "scholarship_id", "field", "is_current"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scholarship_id: Mapped[str] = mapped_column(ForeignKey("scholarships.id", ondelete="CASCADE"))
    field: Mapped[str] = mapped_column(String(64))
    value: Mapped[Any] = mapped_column(JSON)
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    source_key: Mapped[str] = mapped_column(String(80))  # source.key or "dataset:<version>"
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    source_classification: Mapped[str] = mapped_column(String(24))
    snippet: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    extraction_method: Mapped[str] = mapped_column(String(32))  # dataset_import|nsp_listing_parser|html_rules|llm|manual
    verification_status: Mapped[str] = mapped_column(String(24))  # dataset_claim|source_checked|confirmed|conflict|self_reported
    document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_documents.id", ondelete="SET NULL"))
    record_version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    scholarship: Mapped[Scholarship] = relationship(back_populates="evidence")


class ScholarshipSource(Base):
    """Links a scholarship to every source that describes it (multiple sources per opportunity)."""

    __tablename__ = "scholarship_sources"
    __table_args__ = (UniqueConstraint("source_id", "external_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scholarship_id: Mapped[str] = mapped_column(ForeignKey("scholarships.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    external_key: Mapped[str] = mapped_column(String(300))
    match_method: Mapped[str] = mapped_column(String(32))  # exact_key|auto_similarity|admin|configured
    match_score: Mapped[Optional[float]] = mapped_column(Float)
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    currently_listed: Mapped[bool] = mapped_column(Boolean, default=True)

    scholarship: Mapped[Scholarship] = relationship(back_populates="source_links")
    source: Mapped["Source"] = relationship()


# --------------------------------------------------------------------------- monitoring


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    organization: Mapped[Optional[str]] = mapped_column(String(200))
    classification: Mapped[str] = mapped_column(String(24))  # official|institutional|aggregator|other|fixture
    base_url: Mapped[str] = mapped_column(String(1000))
    target_urls: Mapped[list] = mapped_column(JSON, default=list)
    allowed_url_patterns: Mapped[list] = mapped_column(JSON, default=list)
    connector: Mapped[str] = mapped_column(String(32))  # nsp_listing | html_page | pdf_document
    connector_config: Mapped[dict] = mapped_column(JSON, default=dict)
    parser_version: Mapped[str] = mapped_column(String(16), default="1")
    crawl_frequency_minutes: Mapped[int] = mapped_column(Integer, default=24 * 60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    trust_policy: Mapped[Optional[str]] = mapped_column(Text)
    access_notes: Mapped[Optional[str]] = mapped_column(Text)
    linked_scholarship_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("scholarships.id", ondelete="SET NULL")
    )  # page/pdf monitors that describe exactly one scheme

    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    last_change_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    last_http_status: Mapped[Optional[int]] = mapped_column(Integer)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    health_status: Mapped[str] = mapped_column(String(16), default="unknown")  # unknown|healthy|degraded|failing|paused
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    next_check_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    paused_reason: Mapped[Optional[str]] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(16))  # scheduled | manual | retry | cli
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|succeeded|failed|skipped
    requested_by: Mapped[Optional[str]] = mapped_column(String(36))
    queued_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    pages_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    records_seen: Mapped[int] = mapped_column(Integer, default=0)
    records_matched: Mapped[int] = mapped_column(Integer, default=0)
    candidates_created: Mapped[int] = mapped_column(Integer, default=0)
    changes_detected: Mapped[int] = mapped_column(Integer, default=0)
    error_type: Mapped[Optional[str]] = mapped_column(String(48))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    log: Mapped[list] = mapped_column(JSON, default=list)
    retry_of: Mapped[Optional[str]] = mapped_column(String(36))

    source: Mapped[Source] = relationship()


class SourceDocument(Base):
    """A retrieved document version. Raw bytes are stored on disk under data/snapshots/<sha256>."""

    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="SET NULL"))
    url: Mapped[str] = mapped_column(String(1000), index=True)
    final_url: Mapped[Optional[str]] = mapped_column(String(1000))
    fetched_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    http_status: Mapped[Optional[int]] = mapped_column(Integer)
    content_type: Mapped[Optional[str]] = mapped_column(String(120))
    content_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    text_sha256: Mapped[Optional[str]] = mapped_column(String(64))  # hash of normalized main text
    byte_size: Mapped[Optional[int]] = mapped_column(Integer)
    etag: Mapped[Optional[str]] = mapped_column(String(300))
    last_modified: Mapped[Optional[str]] = mapped_column(String(100))
    storage_path: Mapped[Optional[str]] = mapped_column(String(500))
    text_excerpt: Mapped[Optional[str]] = mapped_column(Text)
    extraction_quality: Mapped[Optional[str]] = mapped_column(String(24))  # ok|low_text|needs_ocr|empty
    not_modified: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------- review


class ChangeEvent(Base):
    __tablename__ = "change_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scholarship_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("scholarships.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="SET NULL"))
    document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_documents.id", ondelete="SET NULL"))
    field: Mapped[str] = mapped_column(String(64))
    change_kind: Mapped[str] = mapped_column(String(16))  # changed | added | removed | new_record | content
    old_value: Mapped[Any] = mapped_column(JSON)
    new_value: Mapped[Any] = mapped_column(JSON)
    materiality: Mapped[str] = mapped_column(String(16))  # material | minor | cosmetic
    detected_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    evidence_snippet: Mapped[Optional[str]] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(32))
    review_status: Mapped[str] = mapped_column(String(16))  # auto_accepted|pending|accepted|rejected|informational
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    review_note: Mapped[Optional[str]] = mapped_column(String(500))
    applied_version: Mapped[Optional[int]] = mapped_column(Integer)


class Candidate(Base):
    """An unapproved record proposed by the crawler or extraction pipeline."""

    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16))  # new | update
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|approved|rejected
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="SET NULL"))
    document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_documents.id", ondelete="SET NULL"))
    external_key: Mapped[Optional[str]] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(300))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # normalized field values
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)  # field -> {snippet, location}
    validation: Mapped[dict] = mapped_column(JSON, default=dict)  # {errors: [], warnings: [], unsupported: []}
    possible_matches: Mapped[list] = mapped_column(JSON, default=list)  # [{scholarship_id, name, score}]
    matched_scholarship_id: Mapped[Optional[str]] = mapped_column(ForeignKey("scholarships.id", ondelete="SET NULL"))
    extraction_method: Mapped[str] = mapped_column(String(32))
    extraction_status: Mapped[str] = mapped_column(String(24), default="not_run")  # not_run|succeeded|failed
    extraction_error: Mapped[Optional[str]] = mapped_column(Text)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(32))
    llm_model: Mapped[Optional[str]] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    review_note: Mapped[Optional[str]] = mapped_column(String(500))


# --------------------------------------------------------------------------- operations


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36))
    actor_email: Mapped[Optional[str]] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[Optional[str]] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)
