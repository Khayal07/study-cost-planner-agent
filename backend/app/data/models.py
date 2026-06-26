"""ORM models for the grounded cost database.

Core idea: **every cost figure is a `CostItem` that references exactly one `Source`.**
Any output (chat or PDF) can therefore trace `CostItem -> Source -> url`.

`scope_level` + `scope_id` make `CostItem` polymorphic: a figure can attach to a
program (tuition), a city (living costs) or a country (visa) without separate tables.
"""
from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.db import Base

# --- controlled vocabularies (kept as plain strings; validated in Python) ---
COST_TYPES = {"tuition", "rent", "food", "transport", "insurance", "visa", "utilities", "hidden_misc"}
PERIODS = {"annual", "monthly", "one_time"}
# "global" applies to scholarships only (a country/university/program-agnostic award);
# CostItem never uses it. scope_id is NULL for global scholarships.
SCOPE_LEVELS = {"program", "university", "city", "country", "global"}
CONFIDENCE = {"sourced", "estimate"}
SOURCE_TYPES = {"official_university", "government", "statistical_portal", "currency_api", "estimate"}
# How a scholarship reduces cost. tuition_waiver/full_tuition cancel tuition; partial_tuition
# uses coverage_pct; stipend/living_grant/fixed_amount are fixed cash amounts.
COVERAGE_TYPES = {
    "full_tuition", "partial_tuition", "tuition_waiver",
    "stipend", "living_grant", "fixed_amount",
}

EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5 via fastembed


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)  # NULL for pure estimates
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(40))
    accessed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    iso_code: Mapped[str] = mapped_column(String(2))
    default_currency: Mapped[str] = mapped_column(String(3))

    cities: Mapped[list["City"]] = relationship(back_populates="country")
    universities: Mapped[list["University"]] = relationship(back_populates="country")


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"))
    name: Mapped[str] = mapped_column(String(120))

    country: Mapped["Country"] = relationship(back_populates="cities")


class University(Base):
    __tablename__ = "universities"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    name: Mapped[str] = mapped_column(String(200))
    official_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)

    country: Mapped["Country"] = relationship(back_populates="universities")
    city: Mapped["City"] = relationship()
    programs: Mapped[list["Program"]] = relationship(back_populates="university")


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id"))
    name: Mapped[str] = mapped_column(String(200))
    field: Mapped[str] = mapped_column(String(120))          # e.g. "Computer Science"
    degree_level: Mapped[str] = mapped_column(String(40))    # bachelor | master
    language: Mapped[str] = mapped_column(String(40))
    duration_years: Mapped[float] = mapped_column(Numeric(3, 1))

    university: Mapped["University"] = relationship(back_populates="programs")


class CostItem(Base):
    __tablename__ = "cost_items"
    # Composite index for the polymorphic scope lookups done on every plan/chat query
    # (repository, retrieval, grounded chat answers all filter on these three columns).
    __table_args__ = (
        Index("ix_cost_items_scope", "scope_level", "scope_id", "cost_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cost_type: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    period: Mapped[str] = mapped_column(String(12))
    scope_level: Mapped[str] = mapped_column(String(12))
    scope_id: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    valid_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)

    source: Mapped["Source"] = relationship()


class Scholarship(Base):
    """A grounded scholarship/award, cited like every cost figure (one `Source` each).

    Reuses the polymorphic scope pattern: an award attaches to a program, university,
    country, or is `global` (scope_id NULL). Eligibility criteria are stored as nullable
    columns / comma-lists; NULL means "no restriction" and is scored as a pass.
    """

    __tablename__ = "scholarships"
    # Mirrors ix_cost_items_scope: every plan gathers awards by (scope_level, scope_id).
    __table_args__ = (
        Index("ix_scholarships_scope", "scope_level", "scope_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(200))
    scope_level: Mapped[str] = mapped_column(String(12))      # program|university|country|global
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL for global
    coverage_type: Mapped[str] = mapped_column(String(20))    # see COVERAGE_TYPES
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    coverage_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)  # e.g. 50.00
    currency: Mapped[str] = mapped_column(String(3))
    period: Mapped[str] = mapped_column(String(12))           # annual | one_time
    # Eligibility (NULL = no restriction)
    degree_levels: Mapped[str | None] = mapped_column(String(120), nullable=True)  # "master,phd"
    fields: Mapped[str | None] = mapped_column(Text, nullable=True)                # comma list
    nationality_rule: Mapped[str | None] = mapped_column(Text, nullable=True)      # tokens; "!"=exclude
    min_gpa: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)    # on a 4.0 scale
    language_requirement: Mapped[str | None] = mapped_column(String(200), nullable=True)
    renewable: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    application_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    documents_required: Mapped[str | None] = mapped_column(Text, nullable=True)    # comma list
    confidence: Mapped[str] = mapped_column(String(10))       # sourced | estimate
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    valid_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)

    source: Mapped["Source"] = relationship()


class KnowledgeChunk(Base):
    """Human-readable summaries embedded for chat retrieval (filled in Phase 4)."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref_type: Mapped[str] = mapped_column(String(20))  # university | program | cost | country
    ref_id: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


APPLICATION_STATUSES = {"planned", "in_progress", "submitted", "accepted", "rejected"}


class User(Base):
    """A registered student. Holds the optional eligibility profile so it persists
    across sessions (the stateless chat/form still work without an account)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    # Saved eligibility profile (optional)
    nationality: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gpa: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    language_test: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    applications: Mapped[list["Application"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Application(Base):
    """A scholarship the student is tracking. Award fields are denormalized so the
    tracker stays intact even if the scholarship dataset is reseeded."""

    __tablename__ = "applications"
    __table_args__ = (Index("ix_applications_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    scholarship_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    program_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scholarship_name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str | None] = mapped_column(String(200), nullable=True)
    university_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    coverage_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    application_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="planned")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="applications")
    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationDocument(Base):
    """A single checklist item for an application (transcript, motivation letter…)."""

    __tablename__ = "application_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    name: Mapped[str] = mapped_column(String(200))
    done: Mapped[bool] = mapped_column(Boolean, default=False)

    application: Mapped["Application"] = relationship(back_populates="documents")


class FxRate(Base):
    __tablename__ = "fx_rates"
    # Index for the cache lookup in CurrencyService.get_rate (base, quote, newest first).
    __table_args__ = (
        Index("ix_fx_rates_lookup", "base", "quote", "as_of_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base: Mapped[str] = mapped_column(String(3))
    quote: Mapped[str] = mapped_column(String(3))
    rate: Mapped[float] = mapped_column(Numeric(18, 8))
    as_of_date: Mapped[date] = mapped_column(Date)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
