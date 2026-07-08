"""Tests for the AI data-collection pipeline (no network — LLM monkeypatched)."""
from __future__ import annotations

import json

import pytest

from app.data.models import CostItem, Country, City, Program, Source, University
from app.pipeline import collector, merge
from app.pipeline.validate import (
    classify_source_type,
    country_tuition_bands,
    validate_entry,
)


# --- fixtures ---

def _seed_minimal(session):
    """One country (EE) with two universities; one existing CS master program."""
    src = Source(url="https://ut.ee/fees", title="Fees", publisher="UT", source_type="official_university")
    session.add(src)
    session.flush()
    ee = Country(name="Estonia", iso_code="EE", default_currency="EUR")
    session.add(ee)
    session.flush()
    tartu = City(country_id=ee.id, name="Tartu")
    tallinn = City(country_id=ee.id, name="Tallinn")
    session.add_all([tartu, tallinn])
    session.flush()
    ut = University(country_id=ee.id, city_id=tartu.id, name="University of Tartu",
                    official_url="https://ut.ee", source_id=src.id)
    taltech = University(country_id=ee.id, city_id=tallinn.id, name="TalTech",
                         official_url="https://taltech.ee", source_id=src.id)
    session.add_all([ut, taltech])
    session.flush()
    cs = Program(university_id=ut.id, name="MSc CS", field="Computer Science",
                 degree_level="master", language="English", duration_years=2.0)
    session.add(cs)
    session.flush()
    session.add(CostItem(cost_type="tuition", amount=6000, currency="EUR", period="annual",
                         scope_level="program", scope_id=cs.id, confidence="sourced", source_id=src.id))
    session.commit()
    return {"country": ee, "ut": ut, "taltech": taltech}


def _raw_entry(**overrides) -> dict:
    base = {
        "program_name": "Medicine (MD)",
        "degree_level": "master",
        "language": "English",
        "duration_years": 6.0,
        "tuition_amount": 12000,
        "tuition_currency": "EUR",
        "tuition_period": "annual",
        "source_url": "https://ut.ee/en/admissions/medicine",
        "source_title": "Medicine — tuition",
        "note": "Non-EU fee",
    }
    base.update(overrides)
    return base


def _validate(raw, bands=None, **kw):
    args = dict(
        field="Medicine",
        country_iso="EE",
        default_currency="EUR",
        university_name="University of Tartu",
        official_url="https://ut.ee",
        bands=bands or {},
    )
    args.update(kw)
    return validate_entry(raw, **args)


# --- parsing ---

def test_parse_json_with_prose_wrapper():
    raw = 'Here is what I found:\n{"program_name": "X", "tuition_amount": "1,200", "duration_years": 2} thanks'
    parsed = collector._parse_result(raw)
    assert parsed["program_name"] == "X"
    assert parsed["tuition_amount"] == 1200.0
    assert parsed["duration_years"] == 2.0


def test_parse_not_offered_passthrough():
    assert collector._parse_result('{"not_offered": true}') == {"not_offered": True}


def test_parse_garbage_returns_none():
    assert collector._parse_result("no json here") is None
    assert collector._parse_result("[1, 2, 3]") is None


# --- validation ---

def test_validate_happy_path_builds_seed_shape():
    program, errors, warnings = _validate(_raw_entry())
    assert errors == []
    assert program["field"] == "Medicine"
    assert program["tuition"]["confidence"] == "sourced"
    assert program["tuition"]["source"]["source_type"] == "official_university"
    assert program["tuition"]["source"]["accessed_date"] == program["tuition"]["valid_as_of"]


def test_validate_rejects_bad_currency():
    _, errors, _ = _validate(_raw_entry(tuition_currency="TRY"))
    assert any("whitelist" in e for e in errors)


def test_validate_rejects_above_band():
    bands = {"EE": (1800.0, 18000.0)}
    _, errors, _ = _validate(_raw_entry(tuition_amount=50000), bands=bands)
    assert any("plausibility band" in e for e in errors)


def test_validate_below_band_warns_only():
    bands = {"EE": (1800.0, 18000.0)}
    program, errors, warnings = _validate(_raw_entry(tuition_amount=0), bands=bands)
    assert errors == []
    assert any("below" in w for w in warnings)


def test_validate_bad_url_downgrades_confidence():
    program, errors, warnings = _validate(_raw_entry(source_url="ftp://weird"))
    assert errors == []
    assert program["tuition"]["confidence"] == "estimate"
    assert program["tuition"]["source"]["url"] is None
    assert program["tuition"]["source"]["source_type"] == "estimate"


def test_validate_duration_bounds_and_default():
    _, errors, _ = _validate(_raw_entry(duration_years=12))
    assert any("duration_years" in e for e in errors)
    program, errors, warnings = _validate(_raw_entry(duration_years=None))
    assert errors == []
    assert program["duration_years"] == 2.0  # master default
    assert any("defaulted" in w for w in warnings)


def test_classify_source_type():
    assert classify_source_type("https://www.tum.de/fees", "https://tum.de", "TU Munich") == "official_university"
    assert classify_source_type("https://mastersportal.com/x", "https://ut.ee", "University of Tartu") == "statistical_portal"
    # University name token in host counts as official even without official_url match.
    assert classify_source_type("https://tartu-university.edu/fees", None, "University of Tartu") == "official_university"


def test_country_tuition_bands(db_session):
    _seed_minimal(db_session)
    bands = country_tuition_bands(db_session)
    assert bands["EE"] == (6000 * 0.3, 6000 * 3.0)


# --- target planning / dedupe ---

def test_plan_targets_skips_existing_field_and_staged(db_session):
    _seed_minimal(db_session)
    targets = collector.plan_targets(
        db_session, field="Computer Science", degree="master", country_iso="EE", limit=None, staging={}
    )
    assert [t["university"] for t in targets] == ["TalTech"]  # UT already has CS master

    staging = {"entries": [{"university": "TalTech", "status": "not_offered"}]}
    targets = collector.plan_targets(
        db_session, field="Computer Science", degree="master", country_iso="EE", limit=None, staging=staging
    )
    assert targets == []


def test_plan_targets_new_field_hits_all(db_session):
    _seed_minimal(db_session)
    targets = collector.plan_targets(
        db_session, field="Medicine", degree=None, country_iso="EE", limit=None, staging={}
    )
    assert len(targets) == 2


# --- collect: cap + plan-only ---

def test_collect_respects_cap(db_session, tmp_path, monkeypatch):
    _seed_minimal(db_session)
    calls = {"n": 0}

    def fake_fetch(prompt):
        calls["n"] += 1
        return json.dumps(_raw_entry())

    monkeypatch.setattr(collector, "_fetch_one", fake_fetch)
    monkeypatch.setattr(collector.settings, "pipeline_max_calls", 1)
    monkeypatch.setattr(type(collector.settings), "use_openai", property(lambda self: True), raising=False)
    monkeypatch.setattr(collector, "SEED_DIR", tmp_path)

    result = collector.collect(db_session, field="Medicine", country_iso="EE")
    assert calls["n"] == 1
    assert result["truncated"] is True
    staged = json.loads((tmp_path / "staging" / "medicine.json").read_text(encoding="utf-8"))
    assert len(staged["entries"]) == 1
    assert staged["entries"][0]["status"] == "pending"


def test_collect_plan_only_makes_no_calls(db_session, tmp_path, monkeypatch):
    _seed_minimal(db_session)

    def boom(prompt):
        raise AssertionError("plan-only must not call the API")

    monkeypatch.setattr(collector, "_fetch_one", boom)
    monkeypatch.setattr(collector, "SEED_DIR", tmp_path)
    result = collector.collect(db_session, field="Medicine", country_iso="EE", plan_only=True)
    assert result["calls_made"] == 0
    assert len(result["targets"]) == 2
    assert not (tmp_path / "staging" / "medicine.json").exists()


def test_collect_records_not_offered(db_session, tmp_path, monkeypatch):
    _seed_minimal(db_session)
    monkeypatch.setattr(collector, "_fetch_one", lambda p: '{"not_offered": true}')
    monkeypatch.setattr(type(collector.settings), "use_openai", property(lambda self: True), raising=False)
    monkeypatch.setattr(collector, "SEED_DIR", tmp_path)

    collector.collect(db_session, field="Medicine", country_iso="EE")
    staged = json.loads((tmp_path / "staging" / "medicine.json").read_text(encoding="utf-8"))
    assert {e["status"] for e in staged["entries"]} == {"not_offered"}
    # Re-run: everything staged -> no new calls, nothing to do.
    result = collector.collect(db_session, field="Medicine", country_iso="EE")
    assert result["calls_made"] == 0


# --- merge into seed JSON ---

def _mini_seed() -> dict:
    return {
        "countries": [
            {
                "name": "Estonia",
                "universities": [
                    {"name": "University of Tartu", "programs": [
                        {"name": "MSc CS", "field": "Computer Science", "degree_level": "master"}
                    ]}
                ],
            }
        ]
    }


def test_merge_program_into_seed_and_duplicate():
    data = _mini_seed()
    program, _, _ = _validate(_raw_entry())
    assert merge.merge_program_into_seed(data, "Estonia", "University of Tartu", program) is True
    assert len(data["countries"][0]["universities"][0]["programs"]) == 2
    # Same field+degree again -> duplicate, not re-added.
    assert merge.merge_program_into_seed(data, "Estonia", "University of Tartu", program) is False
    # Unknown university -> False.
    assert merge.merge_program_into_seed(data, "Estonia", "Nowhere U", program) is False


# --- apply: staging -> DB + JSON ---

def test_apply_staging_inserts_db_and_updates_json(db_session, tmp_path):
    refs = _seed_minimal(db_session)
    seed_path = tmp_path / "data.real.json"
    seed_path.write_text(json.dumps(_mini_seed()), encoding="utf-8")

    staging = {
        "schema_version": 1,
        "mode": "new_field",
        "field": "Medicine",
        "entries": [
            {
                "country": "Estonia",
                "country_iso": "EE",
                "university": "University of Tartu",
                "status": "pending",
                "validation": {"errors": [], "warnings": []},
                "raw": _raw_entry(),
            },
            {
                "country": "Estonia",
                "country_iso": "EE",
                "university": "TalTech",
                "status": "not_offered",
                "validation": {"errors": [], "warnings": []},
                "raw": {"not_offered": True},
            },
        ],
    }
    staging_path = tmp_path / "medicine.json"
    staging_path.write_text(json.dumps(staging), encoding="utf-8")

    summary = merge.apply_staging(db_session, staging_path, seed_path=seed_path)
    assert summary == {"applied": 1, "skipped_duplicate": 0, "rejected": 0, "not_offered": 1, "untouched": 0}

    # DB: new Program + tuition CostItem + its own Source.
    prog = db_session.query(Program).filter(Program.field == "Medicine").one()
    assert prog.university_id == refs["ut"].id
    cost = db_session.query(CostItem).filter(
        CostItem.scope_level == "program", CostItem.scope_id == prog.id
    ).one()
    assert float(cost.amount) == 12000
    src = db_session.get(Source, cost.source_id)
    assert src.url == "https://ut.ee/en/admissions/medicine"

    # JSON: program appended; staging statuses flipped.
    seed_after = json.loads(seed_path.read_text(encoding="utf-8"))
    programs = seed_after["countries"][0]["universities"][0]["programs"]
    assert any(p["field"] == "Medicine" for p in programs)
    staging_after = json.loads(staging_path.read_text(encoding="utf-8"))
    assert staging_after["entries"][0]["status"] == "applied"

    # Re-apply: nothing pending anymore.
    summary2 = merge.apply_staging(db_session, staging_path, seed_path=seed_path)
    assert summary2["applied"] == 0
    assert summary2["untouched"] == 1  # the applied entry


def test_apply_rejects_hand_edited_invalid_entry(db_session, tmp_path):
    _seed_minimal(db_session)
    seed_path = tmp_path / "data.real.json"
    seed_path.write_text(json.dumps(_mini_seed()), encoding="utf-8")
    staging = {
        "field": "Medicine",
        "entries": [{
            "country": "Estonia", "country_iso": "EE", "university": "University of Tartu",
            "status": "pending", "validation": {"errors": [], "warnings": []},
            "raw": _raw_entry(tuition_currency="XXX"),  # not whitelisted
        }],
    }
    staging_path = tmp_path / "medicine.json"
    staging_path.write_text(json.dumps(staging), encoding="utf-8")

    summary = merge.apply_staging(db_session, staging_path, seed_path=seed_path)
    assert summary["rejected"] == 1
    assert db_session.query(Program).filter(Program.field == "Medicine").count() == 0
