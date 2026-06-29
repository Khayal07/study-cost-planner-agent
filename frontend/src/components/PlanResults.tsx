"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import {
  createApplication,
  exportPdf,
  type CandidatePlan,
  type PlanResult,
  type ScholarshipMatch,
} from "@/lib/api";
import { useChartColors } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import { CitationChip } from "./CitationChip";
import { ScholarshipPanel } from "./ScholarshipPanel";

// The total to display/rank by: net (after best scholarship) in value mode, else gross.
function displayedTotal(c: CandidatePlan, valueMode: boolean): number {
  return valueMode && c.net_total_annual != null ? c.net_total_annual : c.total_annual;
}

function money(n: number, cur: string) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
}

export function PlanResults({ plan, request }: { plan: PlanResult; request: PlanResult["request"] }) {
  const cur = plan.report_currency;
  const [selected, setSelected] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [rankBy, setRankBy] = useState<"cost" | "value">("cost");
  const [tracked, setTracked] = useState<Set<number>>(new Set());
  const colors = useChartColors();
  const reduce = useReducedMotion();
  const { isAuthed, openAuth } = useAuth();

  async function trackScholarship(m: ScholarshipMatch, candidate: CandidatePlan) {
    if (!isAuthed) {
      openAuth();
      return;
    }
    try {
      await createApplication({
        scholarship_id: m.scholarship_id,
        program_id: candidate.program_id,
        scholarship_name: m.name,
        provider: m.provider,
        university_name: candidate.university_name,
        coverage_type: m.coverage_type,
        estimated_value: m.estimated_value,
        currency: candidate.report_currency,
        deadline: m.deadline,
        application_url: m.application_url,
        documents: m.documents_required,
      });
      setTracked((prev) => new Set(prev).add(m.scholarship_id));
    } catch {
      /* surfaced via disabled state staying off; user can retry */
    }
  }

  if (plan.candidates.length === 0) {
    return (
      <div className="card flex min-h-[300px] flex-col items-center justify-center p-10 text-center">
        <h3 className="font-display text-lg font-semibold">No matching programs</h3>
        <p className="mt-1.5 max-w-xs text-sm text-muted">
          Try clearing the country filter or widening your field of study.
        </p>
      </div>
    );
  }

  const valueMode = rankBy === "value";
  const hasScholarships = plan.candidates.some((c) => c.scholarships && c.scholarships.length > 0);
  const ordered = valueMode
    ? [...plan.candidates].sort((a, b) => (a.value_rank ?? 999) - (b.value_rank ?? 999))
    : plan.candidates;

  const chartData = ordered.map((c) => ({
    name: c.university_name.split(" ").slice(0, 2).join(" "),
    total: displayedTotal(c, valueMode),
    affordable: valueMode ? c.net_affordable ?? c.affordable : c.affordable,
  }));
  const top = ordered[selected] ?? ordered[0];

  function pick(i: number) {
    setSelected(i);
  }

  async function doExport() {
    setExporting(true);
    try {
      // Export a report for the selected university only (backend restricts to it).
      await exportPdf({
        ...request,
        focus_program_id: top?.program_id ?? null,
      });
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Header + PDF */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-semibold tracking-tight">Ranked options</h2>
          <p className="text-sm text-muted">
            {plan.candidates.length} programs · totals in{" "}
            <span className="figure font-medium text-foreground">{cur}</span>
          </p>
          <p className="mt-0.5 text-xs text-muted">
            PDF features{" "}
            <span className="font-medium text-foreground">{top.university_name}</span>
            <span className="hidden sm:inline"> · select a card below to change</span>
          </p>
          {hasScholarships && (
            <div
              role="radiogroup"
              aria-label="Rank by"
              className="mt-2 inline-flex gap-1 rounded-xl border border-border bg-surface-2 p-1"
            >
              {([
                { id: "cost", label: "Cost" },
                { id: "value", label: "Value after aid" },
              ] as const).map((o) => (
                <button
                  key={o.id}
                  type="button"
                  role="radio"
                  aria-checked={rankBy === o.id}
                  onClick={() => {
                    setRankBy(o.id);
                    setSelected(0);
                  }}
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
                    rankBy === o.id ? "bg-surface text-foreground shadow-sm" : "text-muted hover:text-foreground"
                  }`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <button onClick={doExport} disabled={exporting} className="btn-ghost" title={`Export a report for ${top.university_name}`}>
          {exporting ? (
            <Spinner />
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 3v12M7 10l5 5 5-5M5 21h14" />
            </svg>
          )}
          {exporting ? "Generating…" : "Export PDF"}
        </button>
      </div>

      {/* Recommendations */}
      {plan.recommendations.length > 0 && (
        <div className="card border-primary/25 bg-primary-weak/40 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1h6c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2Z" />
            </svg>
            What this means for you
          </div>
          <ul className="space-y-1.5 text-sm">
            {plan.recommendations.map((r, i) => (
              <li key={i} className="flex gap-2 leading-relaxed">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Comparison chart */}
      <div className="card p-4 sm:p-5">
        <h3 className="mb-1 text-sm font-semibold">
          {valueMode ? "Annual cost after scholarships" : "Annual total by option"}
        </h3>
        <p className="mb-4 flex items-center gap-3 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-primary" /> within budget
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: colors.muted }} /> over budget
          </span>
        </p>
        <div
          role="img"
          aria-label={`Bar chart of annual ${valueMode ? "cost after scholarships" : "total"} for ${chartData
            .map((d) => `${d.name}: ${money(d.total, cur)}, ${d.affordable ? "within budget" : "over budget"}`)
            .join("; ")}.`}
        >
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <defs>
              <linearGradient id="barAffordable" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={colors.primary} stopOpacity={0.95} />
                <stop offset="100%" stopColor={colors.primary} stopOpacity={0.55} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={colors.grid} strokeDasharray="3 3" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: colors.axis }}
              interval={0}
              angle={-12}
              textAnchor="end"
              height={52}
              tickLine={false}
              axisLine={{ stroke: colors.grid }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: colors.axis }}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => (v >= 1000 ? `${Math.round(v / 1000)}k` : `${v}`)}
            />
            <Tooltip cursor={{ fill: colors.primary, fillOpacity: 0.06 }} content={<ChartTooltip cur={cur} />} />
            <Bar dataKey="total" radius={[6, 6, 0, 0]} maxBarSize={56}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.affordable ? "url(#barAffordable)" : colors.muted} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        </div>
        {/* Screen-reader / no-JS data table fallback */}
        <table className="sr-only">
          <caption>{valueMode ? "Annual cost after scholarships" : "Annual total by option"}</caption>
          <thead>
            <tr>
              <th scope="col">Option</th>
              <th scope="col">Annual total ({cur})</th>
              <th scope="col">Budget status</th>
            </tr>
          </thead>
          <tbody>
            {chartData.map((d) => (
              <tr key={d.name}>
                <th scope="row">{d.name}</th>
                <td>{money(d.total, cur)}</td>
                <td>{d.affordable ? "within budget" : "over budget"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Ranked candidate selector */}
      <motion.div
        className="grid gap-3 sm:grid-cols-2"
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: reduce ? 0 : 0.05 } } }}
      >
        {ordered.map((c, i) => (
          <motion.div
            key={c.program_id}
            variants={{
              hidden: { opacity: 0, y: reduce ? 0 : 12 },
              show: { opacity: 1, y: 0 },
            }}
            transition={{ duration: reduce ? 0 : 0.3, ease: [0.16, 1, 0.3, 1] }}
          >
            <CandidateRow
              c={c}
              cur={cur}
              valueMode={valueMode}
              selected={i === selected}
              onClick={() => pick(i)}
            />
          </motion.div>
        ))}
      </motion.div>

      {/* Detailed breakdown */}
      <Breakdown c={top} cur={cur} />

      {/* Scholarships for the selected university */}
      <ScholarshipPanel candidate={top} onTrack={trackScholarship} trackedIds={tracked} />

      {/* Verification */}
      {plan.verification && <Verification report={plan.verification} />}

      <p className="px-1 text-[11px] leading-relaxed text-muted">{plan.disclaimer}</p>
    </div>
  );
}

type ChartDatum = { total: number; affordable: boolean };
type ChartTooltipProps = {
  active?: boolean;
  payload?: { payload: ChartDatum }[];
  label?: string;
  cur: string;
};

function ChartTooltip({ active, payload, label, cur }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{label}</p>
      <p className="figure mt-0.5 text-sm font-semibold text-foreground">{money(d.total, cur)}/yr</p>
      <p className={`text-[11px] font-medium ${d.affordable ? "text-primary" : "text-danger"}`}>
        {d.affordable ? "within budget" : "over budget"}
      </p>
    </div>
  );
}

function CandidateRow({
  c,
  cur,
  selected,
  valueMode,
  onClick,
}: {
  c: CandidatePlan;
  cur: string;
  selected: boolean;
  valueMode: boolean;
  onClick: () => void;
}) {
  const rankNum = valueMode ? c.value_rank ?? c.rank : c.rank;
  const affordable = valueMode ? c.net_affordable ?? c.affordable : c.affordable;
  const gap = valueMode ? c.net_budget_gap ?? c.budget_gap : c.budget_gap;
  const total = displayedTotal(c, valueMode);
  const hasAid = c.total_scholarship_value > 0;
  return (
    <button
      onClick={onClick}
      aria-pressed={selected}
      className={`group rounded-2xl border p-4 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${
        selected
          ? "border-primary bg-primary-weak/40 shadow-glow"
          : "border-border bg-surface hover:border-primary/40"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="figure grid h-6 min-w-6 place-items-center rounded-lg bg-surface-2 px-1.5 text-xs font-semibold text-muted">
          #{rankNum}
        </span>
        <span
          className={`chip ${
            affordable ? "bg-primary-weak text-primary" : "bg-danger/10 text-danger"
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${affordable ? "bg-primary" : "bg-danger"}`} />
          {affordable ? "within budget" : "over budget"}
        </span>
      </div>
      <div className="mt-2.5 text-sm font-semibold leading-tight">{c.university_name}</div>
      <div className="text-xs text-muted">{c.city_name}, {c.country_name}</div>
      {hasAid && (
        <div className="mt-2">
          <span className="chip bg-accent-weak text-accent">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M22 10 12 5 2 10l10 5 10-5Z" /><path d="M6 12v5c0 1 2.5 2.5 6 2.5s6-1.5 6-2.5v-5" />
            </svg>
            aid ~{money(c.total_scholarship_value, cur)}/yr
          </span>
        </div>
      )}
      <div className="mt-3 flex items-end justify-between border-t border-border pt-3">
        <div>
          <div className="text-[11px] text-muted">{valueMode ? "After aid / year" : "Total / year"}</div>
          <div className="figure text-base font-semibold">{money(total, cur)}</div>
          {!valueMode && hasAid && c.net_total_annual != null && (
            <div className="figure text-[11px] text-primary">after aid ~{money(c.net_total_annual, cur)}</div>
          )}
        </div>
        <div className="text-right">
          <div className="text-[11px] text-muted">Budget gap</div>
          <div className={`figure text-sm font-semibold ${gap != null && gap >= 0 ? "text-primary" : "text-danger"}`}>
            {gap != null ? money(gap, cur) : "—"}
          </div>
        </div>
      </div>
    </button>
  );
}

function Breakdown({ c, cur }: { c: CandidatePlan; cur: string }) {
  return (
    <div className="card p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-display text-base font-semibold">
          {c.university_name} <span className="font-sans text-sm font-normal text-muted">· {c.city_name}</span>
        </h3>
        <span className="text-xs text-muted">
          Monthly living ~<span className="figure font-medium text-foreground">{money(c.monthly_living, cur)}</span>
        </span>
      </div>

      {c.fx_notes.length > 0 && (
        <div className="mb-4 flex gap-2 rounded-xl border border-accent/30 bg-accent-weak px-3 py-2 text-[12px] text-accent">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-px shrink-0" aria-hidden="true">
            <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
          </svg>
          <span>{c.fx_notes.join(" · ")}</span>
        </div>
      )}

      <div className="-mx-1 overflow-x-auto">
        <table className="w-full text-sm">
          <tbody>
            {c.lines.map((ln, i) => (
              <tr key={i} className="border-b border-border/70 last:border-0">
                <td className="py-2 pl-1 pr-2">{ln.label}</td>
                <td className="figure whitespace-nowrap py-2 text-right font-medium">
                  {money(ln.amount, cur)}
                  {ln.converted && (
                    <span className="ml-1 text-[10px] font-normal text-muted">
                      (from {money(ln.original_amount, ln.original_currency)})
                    </span>
                  )}
                </td>
                <td className="py-2 pl-3 pr-1 text-right">
                  <CitationChip citation={ln.citation} confidence={ln.confidence} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Scenarios */}
      <div className="mt-5">
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Lifestyle scenarios</h4>
        <div className="grid grid-cols-3 gap-2.5">
          {c.scenarios.map((s) => (
            <div key={s.name} className="rounded-xl border border-border bg-surface-2/50 p-3 text-center transition-colors hover:border-primary/40">
              <div className="text-[11px] font-medium capitalize text-muted">{s.name}</div>
              <div className="figure mt-1 text-sm font-semibold">{money(s.annual_total, cur)}</div>
              <div className={`figure mt-0.5 text-[11px] ${s.budget_gap >= 0 ? "text-primary" : "text-danger"}`}>
                {s.budget_gap >= 0 ? "+" : ""}{money(s.budget_gap, cur)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Verification({ report }: { report: PlanResult["verification"] }) {
  if (!report) return null;
  const tone =
    report.overall === "pass" ? "text-primary" : report.overall === "warn" ? "text-accent" : "text-danger";
  const dot = (status: string) =>
    status === "pass" ? "bg-primary" : status === "warn" ? "bg-accent" : "bg-danger";

  return (
    <div className="card p-4 sm:p-5">
      <div className="mb-3 flex items-center gap-2">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={tone} aria-hidden="true">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
        <h3 className="text-sm font-semibold">Data verification</h3>
        <span className={`chip ml-auto bg-surface-2 font-semibold ${tone}`}>{report.overall.toUpperCase()}</span>
      </div>
      {report.summary && <p className="mb-3 text-xs leading-relaxed text-muted">{report.summary}</p>}
      <ul className="space-y-2">
        {report.checks.map((ch) => (
          <li key={ch.name} className="flex gap-2.5 text-xs leading-relaxed">
            <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${dot(ch.status)}`} />
            <span>
              <b className="font-semibold capitalize">{ch.name.replace(/_/g, " ")}</b>
              <span className="text-muted"> — {ch.detail}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4Z" />
    </svg>
  );
}
