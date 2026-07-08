"""Cost forecast: deterministic inflation projection + optional AI commentary.

The math is fully deterministic (compounded static per-country assumptions from
app.data.inflation) so the chart never depends on the LLM. Commentary is a
short, optional extra that degrades to None when the LLM is disabled or slow.
"""
from __future__ import annotations

from datetime import date

from app.core.llm_client import llm
from app.core.schemas import ForecastAssumptions, ForecastRequest, ForecastResponse, ForecastYear
from app.core.text import sanitize_prompt_field
from app.data.inflation import rates_for

_COMMENTARY_SYSTEM = (
    "You are a study-abroad cost advisor. Given a multi-year cost projection, write 2-3 "
    "short sentences of practical budgeting advice for a student. Mention the growth in "
    "concrete terms. Do not invent figures beyond those given. "
)
_LANG_INSTRUCTION = {
    "en": "Write in English.",
    "az": "Write in Azerbaijani (Azərbaycan dilində yaz).",
}


def build_forecast(request: ForecastRequest) -> ForecastResponse:
    rates = rates_for(request.country_iso)
    t_pct = float(rates["tuition_pct"])
    l_pct = float(rates["living_pct"])

    base_year = date.today().year
    series: list[ForecastYear] = []
    for n in range(request.years + 1):
        tuition = round(request.annual_tuition * (1 + t_pct / 100) ** n, 2)
        living = round(request.annual_living * (1 + l_pct / 100) ** n, 2)
        series.append(
            ForecastYear(
                year_offset=n,
                year_label=str(base_year + n),
                tuition=tuition,
                living=living,
                total=round(tuition + living, 2),
            )
        )

    assumptions = ForecastAssumptions(
        tuition_inflation_pct=t_pct,
        living_inflation_pct=l_pct,
        note=str(rates["note"]),
    )

    commentary = None
    if request.with_commentary and llm.enabled:
        commentary = _commentary(request, series, assumptions)

    return ForecastResponse(series=series, assumptions=assumptions, commentary=commentary)


def _commentary(
    request: ForecastRequest, series: list[ForecastYear], assumptions: ForecastAssumptions
) -> str | None:
    country = sanitize_prompt_field(request.country_name, max_len=80)
    currency = sanitize_prompt_field(request.currency, max_len=3).upper()
    first, last = series[0], series[-1]
    user = (
        f"Country: {country}. Currency: {currency}.\n"
        f"Assumed inflation: tuition {assumptions.tuition_inflation_pct}%/yr, "
        f"living {assumptions.living_inflation_pct}%/yr. {assumptions.note}\n"
        f"Today: tuition {first.tuition:.0f}, living {first.living:.0f}, total {first.total:.0f}.\n"
        f"In {last.year_offset} years ({last.year_label}): tuition {last.tuition:.0f}, "
        f"living {last.living:.0f}, total {last.total:.0f}.\n"
        f"{_LANG_INSTRUCTION.get(request.language, _LANG_INSTRUCTION['en'])}"
    )
    return llm.complete_text(_COMMENTARY_SYSTEM, user, max_tokens=180)
