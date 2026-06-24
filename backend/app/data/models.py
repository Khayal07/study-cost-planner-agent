"""ORM models for the grounded cost database.

Core idea: **every cost figure is a `CostItem` that references exactly one `Source`.**
Any output (chat or PDF) can therefore trace `CostItem -> Source -> url`.

`scope_level` + `scope_id` make `CostItem` polymorphic: a figure can attach to a
program (tuition), a city (living costs) or a country (visa) without separate tables.
"""
from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.db import Base

# --- controlled vocabularies (kept as plain strings; validated in Python) ---
COST_TYPES = {"tuition", "rent", "food", "transport", "insurance", "visa", "utilities", "hidden_misc"}
PERIODS = {"annual", "monthly", "one_time"}
SCOPE_LEVELS = {"program", "university", "city", "country"}
CONFIDENCE = {"sourced", "estimate"}
SOURCE_TYPES = {"official_university", "government", "statistical_portal", "currency_api", "estimate"}

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


class KnowledgeChunk(Base):
    """Human-readable summaries embedded for chat retrieval (filled in Phase 4)."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref_type: Mapped[str] = mapped_column(String(20))  # university | program | cost | country
    ref_id: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class FxRate(Base):
    __tablename__ = "fx_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    base: Mapped[str] = mapped_column(String(3))
    quote: Mapped[str] = mapped_column(String(3))
    rate: Mapped[float] = mapped_column(Numeric(18, 8))
    as_of_date: Mapped[date] = mapped_column(Date)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
