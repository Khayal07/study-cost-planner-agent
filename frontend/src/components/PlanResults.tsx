"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { exportPdf, type CandidatePlan, type PlanResult } from "@/lib/api";
import { CitationChip } from "./CitationChip";

function money(n: number, cur: string) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
}

export function PlanResults({ plan, request }: { plan: PlanResult; request: PlanResult["request"] }) {
  const cur = plan.report_currency;
  const [selected, setSelected] = useState(0);
  const [exporting, setExporting] = useState(false);

  if (plan.candidates.length === 0) {
    return <p className="text-muted">No matching programs. Try widening your filters.</p>;
  }

  const chartData = plan.candidates.map((c) => ({
    name: `${c.university_name.split(" ").slice(0, 2).join(" ")}`,
    total: c.total_annual,
    affordable: c.affordable,
  }));

  const top = plan.candidates[selected];

  async function doExport() {
    setExporting(true);
    try {
      await exportPdf({ ...request, max_results: 8 });
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Header + PDF */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Results ({cur})</h2>
        <button
          onClick={doExport}
          disabled={exporting}
          className="rounded-lg border border-brand px-3 py-1.5 text-sm font-medium text-brand hover:bg-brand hover:text-white disabled:opacity-50"
        >
          {exporting ? "Generating…" : "⬇ Export PDF"}
        </button>
      </div>

      {/* Recommendations */}
      {plan.recommendations.length > 0 && (
        <ul className="space-y-1 rounded-xl border border-slate-200 bg-white p-4 text-sm">
          {plan.recommendations.map((r, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-brand">•</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Comparison chart */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="mb-2 text-sm font-medium text-muted">Annual total by option (blue = within budget)</h3>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
            <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-12} textAnchor="end" height={50} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: number) => money(v, cur)} />
            <Bar dataKey="total" radius={[4, 4, 0, 0]}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.affordable ? "#1f6feb" : "#cbd5e1"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Ranked candidate selector */}
      <div className="grid gap-2 sm:grid-cols-2">
        {plan.candidates.map((c, i) => (
          <CandidateRow
            key={c.program_id}
            c={c}
            cur={cur}
            selected={i === selected}
            onClick={() => setSelected(i)}
          />
        ))}
      </div>

      {/* Detailed breakdown for selected candidate */}
      <Breakdown c={top} cur={cur} />

      {/* Verification */}
      {plan.verification && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold">
            Verification —{" "}
            <span className={plan.verification.overall === "pass" ? "text-emerald-600" : "text-amber-600"}>
              {plan.verification.overall.toUpperCase()}
            </span>
          </h3>
          <ul className="space-y-1 text-xs text-slate-600">
            {plan.verification.checks.map((ch) => (
              <li key={ch.name}>
                <span
                  className={
                    ch.status === "pass"
                      ? "text-emerald-600"
                      : ch.status === "warn"
                      ? "text-amber-600"
                      : "text-red-600"
                  }
                >
                  [{ch.status}]
                </span>{" "}
                <b>{ch.name}</b>: {ch.detail}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-[11px] text-muted">{plan.disclaimer}</p>
    </div>
  );
}

function CandidateRow({
  c,
  cur,
  selected,
  onClick,
}: {
  c: CandidatePlan;
  cur: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border p-3 text-left transition ${
        selected ? "border-brand bg-brand/5" : "border-slate-200 bg-white hover:border-slate-300"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted">#{c.rank}</span>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
            c.affordable ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
          }`}
        >
          {c.affordable ? "within budget" : "over budget"}
        </span>
      </div>
      <div className="mt-1 text-sm font-medium leading-tight">{c.university_name}</div>
      <div className="text-xs text-muted">
        {c.city_name}, {c.country_name}
      </div>
      <div className="mt-2 flex justify-between text-xs">
        <span className="text-muted">Total/yr</span>
        <span className="font-semibold">{money(c.total_annual, cur)}</span>
      </div>
      <div className="flex justify-between text-xs">
        <span className="text-muted">Budget gap</span>
        <span className={c.budget_gap != null && c.budget_gap >= 0 ? "text-emerald-600" : "text-red-600"}>
          {c.budget_gap != null ? money(c.budget_gap, cur) : "—"}
        </span>
      </div>
    </button>
  );
}

function Breakdown({ c, cur }: { c: CandidatePlan; cur: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">
          Breakdown — {c.university_name} ({c.city_name})
        </h3>
        <span className="text-xs text-muted">
          Monthly living ~{money(c.monthly_living, cur)}
        </span>
      </div>

      {c.fx_notes.length > 0 && (
        <div className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
          FX: {c.fx_notes.join(" · ")}
        </div>
      )}

      <table className="w-full text-sm">
        <tbody>
          {c.lines.map((ln, i) => (
            <tr key={i} className="border-b border-slate-100 last:border-0">
              <td className="py-1.5">{ln.label}</td>
              <td className="py-1.5 text-right font-medium tabular-nums">
                {money(ln.amount, cur)}
                {ln.converted && (
                  <span className="ml-1 text-[10px] text-muted">
                    (from {money(ln.original_amount, ln.original_currency)})
                  </span>
                )}
              </td>
              <td className="py-1.5 pl-3 text-right">
                <CitationChip citation={ln.citation} confidence={ln.confidence} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Scenarios */}
      <div className="mt-4 grid grid-cols-3 gap-2">
        {c.scenarios.map((s) => (
          <div key={s.name} className="rounded-lg border border-slate-200 p-2 text-center">
            <div className="text-xs font-medium capitalize text-muted">{s.name}</div>
            <div className="text-sm font-semibold">{money(s.annual_total, cur)}</div>
            <div className={`text-[11px] ${s.budget_gap >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              gap {money(s.budget_gap, cur)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
