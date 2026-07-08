"""Apply step: merge approved staging entries into data.real.json + the live DB.

Order of operations keeps the two stores consistent: DB rows are added to an
open (uncommitted) session first, the seed JSON is then written atomically, and
only after a successful write does the session commit. No reseed/reset anywhere
— user accounts and tracked applications survive.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Country, Program, University
from app.data.seed import SEED_DIR, _make_cost, _make_source
from app.pipeline.validate import country_tuition_bands, validate_entry


def atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def merge_program_into_seed(data: dict, country_name: str, university_name: str, program: dict) -> bool:
    """Append the program to the university's block in the parsed seed JSON.
    Returns False when the university isn't found or already has the program
    (same field + degree_level, case-insensitive)."""
    for country in data.get("countries", []):
        if country.get("name") != country_name:
            continue
        for uni in country.get("universities", []):
            if uni.get("name") != university_name:
                continue
            for existing in uni.get("programs", []):
                if (
                    existing.get("field", "").lower() == program["field"].lower()
                    and existing.get("degree_level") == program["degree_level"]
                ):
                    return False
            uni.setdefault("programs", []).append(program)
            return True
    return False


def _db_has_program(session: Session, university_name: str, field: str, degree: str) -> bool:
    return (
        session.execute(
            select(Program.id)
            .join(University, Program.university_id == University.id)
            .where(
                University.name == university_name,
                Program.field.ilike(field),
                Program.degree_level == degree,
            )
        ).first()
        is not None
    )


def _insert_into_db(session: Session, university: University, program: dict) -> None:
    prog = Program(
        university_id=university.id,
        name=program["name"],
        field=program["field"],
        degree_level=program["degree_level"],
        language=program["language"],
        duration_years=program["duration_years"],
    )
    session.add(prog)
    session.flush()
    src = _make_source(session, program["tuition"]["source"])
    _make_cost(
        session,
        raw=program["tuition"],
        cost_type="tuition",
        scope_level="program",
        scope_id=prog.id,
        source_id=src.id,
    )


def apply_staging(session: Session, staging_path: Path, seed_path: Path | None = None) -> dict:
    """Apply every reviewable ("pending") entry. Returns a summary dict:
    {applied, skipped_duplicate, rejected, not_offered, untouched}."""
    seed_path = seed_path or (SEED_DIR / "data.real.json")
    staging = json.loads(staging_path.read_text(encoding="utf-8"))
    seed_data = json.loads(seed_path.read_text(encoding="utf-8"))

    field = staging.get("field", "")
    bands = country_tuition_bands(session)
    summary = {"applied": 0, "skipped_duplicate": 0, "rejected": 0, "not_offered": 0, "untouched": 0}

    for entry in staging.get("entries", []):
        status = entry.get("status")
        if status == "not_offered":
            summary["not_offered"] += 1
            continue
        if status != "pending":
            summary["untouched"] += 1
            continue

        university = session.execute(
            select(University).where(University.name == entry.get("university"))
        ).scalar_one_or_none()
        if university is None:
            entry.setdefault("validation", {"errors": [], "warnings": []})
            entry["status"] = "rejected"
            entry["validation"]["errors"].append("university not found in DB")
            summary["rejected"] += 1
            continue
        country = session.get(Country, university.country_id)

        # Re-validate from the raw model output — staging files are hand-editable,
        # so apply never trusts a "pending" flag alone.
        program, errors, warnings = validate_entry(
            entry.get("raw", {}),
            field=field,
            country_iso=country.iso_code if country else "",
            default_currency=country.default_currency if country else "EUR",
            university_name=entry.get("university", ""),
            official_url=university.official_url,
            bands=bands,
        )
        if program is None:
            entry["status"] = "rejected"
            entry["validation"] = {"errors": errors, "warnings": warnings}
            summary["rejected"] += 1
            continue

        if _db_has_program(session, entry["university"], program["field"], program["degree_level"]):
            entry["status"] = "skipped_duplicate"
            summary["skipped_duplicate"] += 1
            continue
        if not merge_program_into_seed(seed_data, entry["country"], entry["university"], program):
            entry["status"] = "skipped_duplicate"
            summary["skipped_duplicate"] += 1
            continue

        _insert_into_db(session, university, program)
        entry["status"] = "applied"
        entry["program"] = program
        summary["applied"] += 1

    if summary["applied"] > 0:
        try:
            atomic_write_json(seed_path, seed_data)
        except OSError:
            session.rollback()
            raise
        session.commit()
    atomic_write_json(staging_path, staging)
    return summary
