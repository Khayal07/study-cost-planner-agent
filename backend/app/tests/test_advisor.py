"""Unit tests for the advisor's deterministic pieces (no DB / no network).

The DB-backed conversation routing is exercised separately; here we lock down the
pure logic: budget-fit scoring, "the second one" reference resolution, and the
enriched slot extraction (degree level, '15k' budgets).
"""
from __future__ import annotations

from app.agents.intent import extract_slots
from app.core.schemas import ChatCandidateRef, ChatProfile
from app.services.chat import _match_score, _resolve_ordinal_program


def test_match_score_rewards_affordability():
    # Well under budget -> safe -> top score; just over -> mid; far over -> low.
    assert _match_score(20000, 10000) == 100        # 2x headroom
    assert _match_score(10000, 10000) == 85          # exactly on budget
    assert _match_score(9000, 10000) == 63           # ~10% over
    assert _match_score(5000, 10000) == 35           # 2x over
    assert _match_score(None, 10000) is None         # no budget -> no score


def _profile_with_candidates() -> ChatProfile:
    return ChatProfile(last_candidates=[
        ChatCandidateRef(rank=1, program_id=11, program_name="A", university_name="Alpha",
                         city_name="X", country_name="C", total_annual=10000),
        ChatCandidateRef(rank=2, program_id=22, program_name="B", university_name="Beta",
                         city_name="Y", country_name="C", total_annual=12000),
        ChatCandidateRef(rank=3, program_id=33, program_name="G", university_name="Gamma",
                         city_name="Z", country_name="C", total_annual=15000),
    ])


def test_ordinal_reference_resolution():
    p = _profile_with_candidates()
    assert _resolve_ordinal_program("tell me about the second one", p) == 22
    assert _resolve_ordinal_program("explore option 3", p) == 33
    assert _resolve_ordinal_program("the cheapest one please", p) == 11   # rank 1
    assert _resolve_ordinal_program("show me the last one", p) == 33
    assert _resolve_ordinal_program("compare them", p) is None            # no ordinal


def test_ordinal_resolution_without_candidates_is_none():
    assert _resolve_ordinal_program("the second one", ChatProfile()) is None


def test_ordinal_does_not_falsely_match_it_inside_words():
    # Regression: "university" contains "it" — naming a university must NOT be read as
    # a back-reference to the first option (which used to return the wrong school).
    p = _profile_with_candidates()
    assert _resolve_ordinal_program("tell me about istanbul technical university", p) is None
    assert _resolve_ordinal_program("what about this last semester", p) is None


def test_extract_slots_degree_and_k_budget():
    slots = extract_slots("I want a master in CS, budget 15k USD", "EUR")
    assert slots["degree_level"] == "master"
    assert slots["field"] == "Computer Science"
    assert slots["budget_amount"] == 15000.0
    assert slots["budget_currency"] == "USD"


def test_extract_slots_absent_fields_are_none():
    slots = extract_slots("hello there", "EUR")
    assert slots["budget_amount"] is None
    assert slots["country"] is None


def test_extract_eligibility_slots():
    slots = extract_slots(
        "I'm from Azerbaijan, my GPA is 3.6 and I have IELTS 7.0", "EUR"
    )
    assert slots["nationality"] == "Azerbaijan"
    assert slots["gpa"] == 3.6
    assert slots["language_test"] == "IELTS 7.0"


def test_gpa_not_confused_with_budget():
    slots = extract_slots("budget 12000 EUR in Poland", "EUR")
    assert slots["gpa"] is None
    assert slots["budget_amount"] == 12000.0


def test_nationality_requires_explicit_cue():
    # "study in Germany" is a destination, not a nationality.
    slots = extract_slots("I want to study in Germany", "EUR")
    assert slots["nationality"] is None
