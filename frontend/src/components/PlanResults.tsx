"use client";

import { useEffect, useRef, useState } from "react";
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
  saveCurrentPlan,
  type CandidatePlan,
  type PlanningRequest,
  type PlanResult,
  type ScholarshipMatch,
} from "@/lib/api";
import { useChartColors } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import { CitationChip } from "./CitationChip";
import { ScholarshipPanel } from "./ScholarshipPanel";
import { ComparisonView } from "./ComparisonView";
import { CostSankey } from "./CostSankey";
import { CashFlowChart } from "./CashFlowChart";
import { CostForecast } from "./CostForecast";
import { ShareCard } from "./ShareCard";

const MAX_PINNED = 3;

// The total to display/rank by: net (after best scholarship) in value mode, else gross.
function displayedTotal(c: CandidatePlan, valueMode: boolean): number {
  return valueMode && c.net_total_annual != null ? c.net_total_annual : c.total_annual;
}

function money(n: number, cur: string) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
}

export function PlanResults({
  plan,
  request,
  refreshing = false,
  onWhatIf,
}: {
  plan: PlanResult;
  request: PlanResult["request"];
  refreshing?: boolean;
  onWhatIf?: (req: PlanningRequest) => void;
}) {
  const cur = plan.report_currency;
  const [selected, setSelected] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [rankBy, setRankBy] = useState<"cost" | "value">("cost");
  const [pinned, setPinned] = useState<number[]>([]);
  const [tracked, setTracked] = useState<Set<number>>(new Set());
  const [showShareCard, setShowShareCard] = useState(false);

  function togglePin(programId: number) {
    setPinned((prev) =>
      prev.includes(programId)
        ? prev.filter((id) => id !== programId)
        : prev.length >= MAX_PINNED
          ? prev
          : [...prev, programId],
    );
  }
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

  async function saveAndShare() {
    if (!isAuthed) {
      openAuth();
      return;
    }
    setSaving(true);
    setCopied(false);
    try {
      const where = request.country ? ` · ${request.country}` : "";
      const title = `${request.field ?? "Study"}${where}`;
      const saved = await saveCurrentPlan(title, request);
      const url = `${window.location.origin}/p/${saved.public_id}`;
      setShareUrl(url);
      try {
        await navigator.clipboard.writeText(url);
        setCopied(true);
      } catch {
        /* clipboard blocked — the link is still shown to copy manually */
      }
    } catch {
      /* leave the button enabled so the user can retry */
    } finally {
      setSaving(false);
    }
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
        <div className="flex shrink-0 gap-2">
          <button onClick={() => setShowShareCard(true)} className="btn-ghost" title={`Share a summary card for ${top.university_name}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="9" cy="9" r="2" /><path d="m21 15-3.5-3.5L9 20" />
            </svg>
            Share card
          </button>
          <button onClick={saveAndShare} disabled={saving} className="btn-ghost" title="Save this plan and get a shareable link">
            {saving ? (
              <Spinner />
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
                <path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" />
              </svg>
            )}
            {saving ? "Saving…" : "Save & share"}
          </button>
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
      </div>

      {/* Shareable link banner */}
      {shareUrl && (
        <div className="card flex flex-wrap items-center gap-3 border-primary/30 bg-primary-weak/30 p-3">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-primary" aria-hidden="true">
            <path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" />
          </svg>
          <input readOnly value={shareUrl} className="input min-w-0 flex-1 text-xs" aria-label="Shareable link" onFocus={(e) => e.currentTarget.select()} />
          <button
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(shareUrl);
                setCopied(true);
              } catch {
                /* ignore */
              }
            }}
            className="btn-primary shrink-0 px-3 py-1.5 text-xs"
          >
            {copied ? "Copied!" : "Copy link"}
          </button>
        </div>
      )}

      {/* What-if controls */}
      {onWhatIf && <WhatIfPanel request={request} refreshing={refreshing} onChange={onWhatIf} />}

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
              pinned={pinned.includes(c.program_id)}
              pinDisabled={pinned.length >= MAX_PINNED && !pinned.includes(c.program_id)}
              onTogglePin={() => togglePin(c.program_id)}
            />
          </motion.div>
        ))}
      </motion.div>

      {/* Side-by-side comparison of pinned candidates */}
      {pinned.length >= 2 && (
        <ComparisonView
          candidates={pinned
            .map((id) => plan.candidates.find((c) => c.program_id === id))
            .filter((c): c is CandidatePlan => Boolean(c))}
          cur={cur}
          onClose={() => setPinned([])}
          onUnpin={(id) => togglePin(id)}
        />
      )}
      {pinned.length === 1 && (
        <p className="px-1 text-xs text-muted">Pin one more option to compare side by side.</p>
      )}

      {/* Detailed breakdown */}
      <Breakdown c={top} cur={cur} />

      {/* Where the money goes (Sankey) */}
      <CostSankey c={top} cur={cur} />

      {/* Month-by-month spend projection */}
      <CashFlowChart c={top} cur={cur} />

      {/* Multi-year cost forecast */}
      <CostForecast c={top} cur={cur} />

      {/* Shareable PNG summary card */}
      {showShareCard && <ShareCard c={top} cur={cur} onClose={() => setShowShareCard(false)} />}

      {/* Part-time work earnings offset */}
      <WorkOffsetCard c={top} cur={cur} />

      {/* Scholarships for the selected university */}
      <ScholarshipPanel
        candidate={top}
        onTrack={trackScholarship}
        trackedIds={tracked}
        onExportLive={(sel, cand) =>
          exportPdf({ ...request, focus_program_id: cand.program_id, extra_scholarships: sel })
        }
      />

      {/* Verification */}
      {plan.verification && <Verification report={plan.verification} />}

      <p className="px-1 text-[11px] leading-relaxed text-muted">{plan.disclaimer}</p>
    </div>
  );
}

const WHATIF_LIFESTYLES = ["frugal", "moderate", "comfortable"] as const;

/** Live "what-if" budget + lifestyle tuning; re-plans (debounced) without losing the view. */
function WhatIfPanel({
  request,
  refreshing,
  onChange,
}: {
  request: PlanningRequest;
  refreshing: boolean;
  onChange: (req: PlanningRequest) => void;
}) {
  const [budget, setBudget] = useState(request.budget_amount);
  const [lifestyle, setLifestyle] = useState(request.lifestyle ?? "moderate");
  const firstRun = useRef(true);

  // Keep the panel in sync if a fresh plan arrives from outside (e.g. new wizard run).
  useEffect(() => {
    setBudget(request.budget_amount);
    setLifestyle(request.lifestyle ?? "moderate");
  }, [request.budget_amount, request.lifestyle]);

  // Debounced re-plan when the user tweaks budget/lifestyle here.
  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    if (budget === request.budget_amount && lifestyle === (request.lifestyle ?? "moderate")) return;
    const t = setTimeout(() => onChange({ ...request, budget_amount: budget, lifestyle }), 450);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [budget, lifestyle]);

  const cur = request.budget_currency;
  const min = 1000;
  const max = Math.max(20000, Math.round((request.budget_amount * 2.5) / 1000) * 1000);

  return (
    <div className="card border-primary/20 bg-primary-weak/20 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary" aria-hidden="true">
            <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
          </svg>
          What-if
        </h3>
        {refreshing && (
          <span className="flex items-center gap-1.5 text-[11px] text-muted">
            <Spinner /> updating…
          </span>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-center">
        <div>
          <div className="mb-1.5 flex items-center justify-between text-[11px]">
            <label htmlFor="whatif-budget" className="font-medium text-muted">Yearly budget</label>
            <span className="figure font-semibold text-foreground">{money(budget, cur)}</span>
          </div>
          <input
            id="whatif-budget"
            type="range"
            min={min}
            max={max}
            step={500}
            value={Math.min(budget, max)}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-border accent-primary"
            aria-valuetext={money(budget, cur)}
          />
        </div>

        <div role="radiogroup" aria-label="Lifestyle" className="grid grid-cols-3 gap-1 rounded-xl border border-border bg-surface-2 p-1">
          {WHATIF_LIFESTYLES.map((l) => (
            <button
              key={l}
              type="button"
              role="radio"
              aria-checked={lifestyle === l}
              onClick={() => setLifestyle(l)}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium capitalize transition-all ${
                lifestyle === l ? "bg-surface text-foreground shadow-sm" : "text-muted hover:text-foreground"
              }`}
            >
              {l}
            </button>
          ))}
        </div>
      </div>
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
  pinned,
  pinDisabled,
  onTogglePin,
}: {
  c: CandidatePlan;
  cur: string;
  selected: boolean;
  valueMode: boolean;
  onClick: () => void;
  pinned: boolean;
  pinDisabled: boolean;
  onTogglePin: () => void;
}) {
  const rankNum = valueMode ? c.value_rank ?? c.rank : c.rank;
  const affordable = valueMode ? c.net_affordable ?? c.affordable : c.affordable;
  const gap = valueMode ? c.net_budget_gap ?? c.budget_gap : c.budget_gap;
  const total = displayedTotal(c, valueMode);
  const hasAid = c.total_scholarship_value > 0;
  return (
    <div className="relative h-full">
      <button
        onClick={onTogglePin}
        disabled={pinDisabled}
        aria-pressed={pinned}
        title={pinned ? "Unpin from comparison" : pinDisabled ? "Pin up to 3 options" : "Pin to compare"}
        className={`absolute right-3 top-3 z-10 grid h-7 w-7 place-items-center rounded-lg border transition-all ${
          pinned
            ? "border-primary bg-primary text-primary-fg shadow-sm"
            : "border-border bg-surface text-muted hover:border-primary/50 hover:text-primary disabled:pointer-events-none disabled:opacity-40"
        }`}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill={pinned ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M9 4v6l-2 4h10l-2-4V4M12 18v3M8 4h8" />
        </svg>
      </button>
    <button
      onClick={onClick}
      aria-pressed={selected}
      className={`group h-full w-full rounded-2xl border p-4 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${
        selected
          ? "border-primary bg-primary-weak/40 shadow-glow"
          : "border-border bg-surface hover:border-primary/40"
      }`}
    >
      <div className="flex items-center justify-between pr-9">
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
    </div>
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

/** Potential part-time work earnings as an optional offset (never auto-applied). */
function WorkOffsetCard({ c, cur }: { c: CandidatePlan; cur: string }) {
  const [applied, setApplied] = useState(false);
  if (c.work_annual_earnings == null || c.work_hours_cap == null) return null;

  const earnings = c.work_annual_earnings;
  const base = c.net_total_annual ?? c.total_annual;
  const usedAid = c.net_total_annual != null && c.total_scholarship_value > 0;
  const effective = Math.max(0, base - earnings);

  return (
    <div className="card p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 font-display text-base font-semibold">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary" aria-hidden="true">
            <rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
          </svg>
          Part-time work
        </h3>
        <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-muted">
          <input type="checkbox" checked={applied} onChange={(e) => setApplied(e.target.checked)} className="h-3.5 w-3.5 accent-primary" />
          Apply to total
        </label>
      </div>

      <p className="mt-2 text-sm">
        Working up to{" "}
        <span className="font-semibold text-foreground">{c.work_hours_cap} h/week</span> could earn about{" "}
        <span className="figure font-semibold text-primary">~{money(earnings, cur)}/yr</span>{" "}
        <span className="text-muted">(gross estimate).</span>
      </p>

      {applied && (
        <div className="mt-3 rounded-xl border border-primary/30 bg-primary-weak/40 p-3 text-sm">
          {usedAid ? "After aid and work" : "After work"}, your effective cost ≈{" "}
          <span className="figure font-semibold text-primary">{money(effective, cur)}/yr</span>
          <span className="text-muted"> (from {money(c.total_annual, cur)}).</span>
        </div>
      )}

      {c.work_note && <p className="mt-2 text-[11px] leading-relaxed text-muted">{c.work_note}</p>}

      <div className="mt-2 flex items-center justify-between gap-2">
        {c.work_citation && <CitationChip citation={c.work_citation} confidence="estimate" />}
        <span className="text-[11px] text-muted">Earnings aren&apos;t guaranteed — treat as a buffer, not budget.</span>
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
