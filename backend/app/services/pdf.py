"""PDF financial-plan export: Matplotlib charts embedded in a WeasyPrint HTML report.

Every figure in the report carries its citation (publisher + URL + sourced/estimate),
matching what the chat/UI shows — one citation contract across all outputs.
"""
from __future__ import annotations

import base64
import io
from html import escape

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402

from app.core.schemas import PlanResult  # noqa: E402


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _comparison_chart(plan: PlanResult) -> str:
    names = [f"{c.university_name[:18]}\n({c.city_name})" for c in plan.candidates]
    totals = [c.total_annual for c in plan.candidates]
    colors = ["#1f6feb" if c.affordable else "#cbd5e1" for c in plan.candidates]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.bar(range(len(names)), totals, color=colors)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, fontsize=7, rotation=0)
    ax.set_ylabel(f"Total / year ({plan.report_currency})", fontsize=8)
    ax.set_title("Annual total cost by option (blue = within budget)", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    return _fig_to_b64(fig)


def _breakdown_chart(top) -> str:
    parts = {
        "Tuition": top.annual_tuition,
        "Living": top.annual_living,
        "One-time": top.annual_one_time,
        "Hidden": top.annual_hidden,
    }
    parts = {k: v for k, v in parts.items() if v > 0}
    fig, ax = plt.subplots(figsize=(4.2, 3.4))
    ax.pie(parts.values(), labels=parts.keys(), autopct="%1.0f%%", textprops={"fontsize": 8},
           colors=["#1f6feb", "#60a5fa", "#fbbf24", "#f87171"])
    ax.set_title(f"Cost breakdown — {top.university_name[:24]}", fontsize=9)
    return _fig_to_b64(fig)


def _citation_html(cit) -> str:
    label = "sourced" if cit.source_type != "estimate" else "estimate"
    if cit.url:
        link = f'<a href="{escape(cit.url)}">{escape(cit.publisher)}</a>'
    else:
        link = escape(cit.publisher)
    acc = f" (accessed {cit.accessed_date})" if cit.accessed_date else ""
    return f"{link}{acc}"


def render_plan_pdf(plan: PlanResult) -> bytes:
    from weasyprint import HTML

    cur = plan.report_currency
    # Feature the university the user selected / asked about; otherwise the top-ranked one.
    top = None
    if plan.candidates:
        focus = plan.request.focus_program_id
        top = next((c for c in plan.candidates if c.program_id == focus), plan.candidates[0])
    is_focused = bool(plan.request.focus_program_id) and top is not None \
        and top.program_id == plan.request.focus_program_id
    # Single-university report: one candidate (a specific school was selected/asked about).
    single = top is not None and len(plan.candidates) == 1

    cmp_chart = _comparison_chart(plan) if plan.candidates and not single else ""
    brk_chart = _breakdown_chart(top) if top else ""

    # Ranked table (only when comparing multiple options)
    rows = ""
    if not single:
        for c in plan.candidates:
            fit = "✓" if c.affordable else "✗"
            rows += (
                f"<tr><td>{c.rank}</td><td>{escape(c.university_name)}</td>"
                f"<td>{escape(c.city_name)}, {escape(c.country_name)}</td>"
                f"<td class='num'>{c.annual_tuition:,.0f}</td>"
                f"<td class='num'>{c.monthly_living:,.0f}</td>"
                f"<td class='num'>{c.total_annual:,.0f}</td>"
                f"<td class='num'>{c.budget_gap:,.0f}</td><td>{fit}</td></tr>"
            )

    # Top candidate line items with citations (the featured university computed above)
    line_rows = ""
    if top:
        for ln in top.lines:
            conv = f" (from {ln.original_amount:,.0f} {ln.original_currency})" if ln.converted else ""
            line_rows += (
                f"<tr><td>{escape(ln.label)}</td>"
                f"<td class='num'>{ln.amount:,.0f} {cur}{conv}</td>"
                f"<td>{ln.confidence}</td><td class='cite'>{_citation_html(ln.citation)}</td></tr>"
            )

    scen_rows = ""
    if top:
        for s in top.scenarios:
            scen_rows += (
                f"<tr><td>{s.name.capitalize()}</td>"
                f"<td class='num'>{s.monthly_living:,.0f} {cur}</td>"
                f"<td class='num'>{s.annual_total:,.0f} {cur}</td>"
                f"<td class='num'>{s.budget_gap:,.0f} {cur}</td></tr>"
            )

    checks = ""
    if plan.verification:
        for ch in plan.verification.checks:
            checks += f"<li><b>{ch.status.upper()}</b> — {escape(ch.name)}: {escape(ch.detail)}</li>"

    recs = "".join(f"<li>{escape(r)}</li>" for r in plan.recommendations)

    req = plan.request
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 1.6cm; }}
      body {{ font-family: 'Helvetica', sans-serif; color: #0f172a; font-size: 11px; }}
      h1 {{ color: #1f6feb; font-size: 20px; margin-bottom: 2px; }}
      h2 {{ font-size: 13px; border-bottom: 2px solid #e2e8f0; padding-bottom: 3px; margin-top: 18px; }}
      .sub {{ color: #64748b; font-size: 11px; }}
      table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
      th, td {{ text-align: left; padding: 4px 6px; border-bottom: 1px solid #eef2f7; font-size: 10px; }}
      th {{ background: #f8fafc; color: #475569; }}
      td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
      td.cite {{ font-size: 8.5px; color: #475569; }}
      .charts {{ display: flex; gap: 10px; margin-top: 8px; }}
      .charts img {{ width: 100%; }}
      .pill {{ display:inline-block; background:#eff6ff; color:#1f6feb; padding:1px 7px; border-radius:8px; font-size:10px; }}
      ul {{ margin: 4px 0; padding-left: 16px; }}
      li {{ font-size: 10px; margin: 2px 0; }}
      .disc {{ color:#64748b; font-size:8.5px; margin-top:14px; border-top:1px solid #e2e8f0; padding-top:6px; }}
    </style></head><body>
      <h1>{'Study Cost Report' if single else 'Study Cost Plan'}</h1>
      <div class="sub">
        {f'{escape(top.university_name)} — {escape(top.city_name)}, {escape(top.country_name)} · '
         if single and top else ''}
        Field: {escape(req.field or 'Any')} ·
        Country: {escape(req.country or 'All')} ·
        Budget: {req.budget_amount:,.0f} {escape(req.budget_currency)}/year ·
        Report currency: {cur}
      </div>
      {f'<div class="sub" style="margin-top:3px"><span class="pill">Focused on</span> '
       f'{escape(top.university_name)} — {escape(top.city_name)}, {escape(top.country_name)}</div>'
       if is_focused and not single else ''}

      {'' if single else f'''<h2>Option comparison</h2>
      <div class="charts">
        <img src="data:image/png;base64,{cmp_chart}"/>
        <img src="data:image/png;base64,{brk_chart}"/>
      </div>
      <table>
        <tr><th>#</th><th>University</th><th>Location</th><th>Tuition/yr</th>
            <th>Living/mo</th><th>Total/yr</th><th>Budget gap</th><th>Fit</th></tr>
        {rows}
      </table>'''}

      {f'''<div class="charts" style="margin-top:8px"><img src="data:image/png;base64,{brk_chart}" style="width:48%"/></div>'''
       if single else ''}

      <h2>Cost breakdown — {escape(top.university_name) if top else ''} <span class="pill">cited</span></h2>
      <table>
        <tr><th>Item</th><th>Amount ({cur}/yr)</th><th>Confidence</th><th>Source</th></tr>
        {line_rows}
      </table>

      <h2>Lifestyle scenarios</h2>
      <table>
        <tr><th>Scenario</th><th>Living/mo</th><th>Total/yr</th><th>Budget gap</th></tr>
        {scen_rows}
      </table>

      <h2>Recommendations</h2>
      <ul>{recs}</ul>

      <h2>Verification — {plan.verification.overall.upper() if plan.verification else 'N/A'}</h2>
      <ul>{checks}</ul>

      <div class="disc">{escape(plan.disclaimer)}<br/>Generated {plan.generated_at:%Y-%m-%d %H:%M} UTC.</div>
    </body></html>"""

    return HTML(string=html).write_pdf()
