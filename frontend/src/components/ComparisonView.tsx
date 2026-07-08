"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { CandidatePlan } from "@/lib/api";
import { CostRadar } from "./CostRadar";

function money(n: number, cur: string) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
}

/** Lowest value wins (cheapest). Returns the index of the minimum, or -1 if tied/empty. */
function bestIndex(values: (number | null)[]): number {
  let best = -1;
  let min = Infinity;
  let ties = 0;
  values.forEach((v, i) => {
    if (v == null) return;
    if (v < min) {
      min = v;
      best = i;
      ties = 1;
    } else if (v === min) {
      ties += 1;
    }
  });
  return ties === 1 ? best : -1;
}

export function ComparisonView({
  candidates,
  cur,
  onClose,
  onUnpin,
}: {
  candidates: CandidatePlan[];
  cur: string;
  onClose: () => void;
  onUnpin: (programId: number) => void;
}) {
  const reduce = useReducedMotion();

  // Union of cost-line labels, preserving the first candidate's order.
  const labels: string[] = [];
  for (const c of candidates) {
    for (const ln of c.lines) if (!labels.includes(ln.label)) labels.push(ln.label);
  }

  const amountFor = (c: CandidatePlan, label: string) =>
    c.lines.find((l) => l.label === label)?.amount ?? null;

  const rows = labels.map((label) => ({
    label,
    values: candidates.map((c) => amountFor(c, label)),
  }));

  const totals = candidates.map((c) => c.total_annual);
  const netTotals = candidates.map((c) => c.net_total_annual ?? c.total_annual);
  const aid = candidates.map((c) => c.total_scholarship_value);
  const monthly = candidates.map((c) => c.monthly_living);

  const bestTotal = bestIndex(totals);
  const bestNet = bestIndex(netTotals);
  const bestMonthly = bestIndex(monthly);
  // Highest aid wins → invert for bestIndex.
  const bestAid = bestIndex(aid.map((v) => -v));

  return (
    <AnimatePresence>
      <motion.section
        initial={{ opacity: 0, y: reduce ? 0 : 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: reduce ? 0 : 12 }}
        transition={{ duration: reduce ? 0 : 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="card overflow-hidden"
        aria-label="Side-by-side comparison"
      >
        <div className="flex items-center justify-between gap-3 border-b border-border bg-surface-2/60 px-4 py-3 sm:px-5">
          <div className="flex items-center gap-2">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary" aria-hidden="true">
              <path d="M3 3v18h18M8 17V9M13 17V5M18 17v-6" />
            </svg>
            <h3 className="font-display text-sm font-semibold">
              Comparing {candidates.length} options
            </h3>
          </div>
          <button onClick={onClose} className="btn-ghost px-2.5 py-1.5 text-xs" aria-label="Close comparison">
            Clear
          </button>
        </div>

        <CostRadar candidates={candidates} cur={cur} />

        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-muted">
                  Cost line
                </th>
                {candidates.map((c) => (
                  <th key={c.program_id} scope="col" className="px-3 py-3 text-left align-top">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-foreground">{c.university_name}</div>
                        <div className="truncate text-[11px] font-normal text-muted">{c.city_name}, {c.country_name}</div>
                      </div>
                      <button
                        onClick={() => onUnpin(c.program_id)}
                        aria-label={`Remove ${c.university_name} from comparison`}
                        className="shrink-0 rounded-md p-0.5 text-muted transition-colors hover:bg-danger/10 hover:text-danger"
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <path d="M18 6 6 18M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const best = bestIndex(r.values);
                return (
                  <tr key={r.label} className="border-b border-border/60">
                    <th scope="row" className="px-4 py-2 text-left text-xs font-normal text-muted">{r.label}</th>
                    {r.values.map((v, i) => (
                      <td
                        key={i}
                        className={`figure px-3 py-2 ${i === best ? "font-semibold text-primary" : "text-foreground"}`}
                      >
                        {v != null ? money(v, cur) : "—"}
                      </td>
                    ))}
                  </tr>
                );
              })}

              <SummaryRow label="Total / year" values={totals} best={bestTotal} cur={cur} strong />
              {aid.some((v) => v > 0) && (
                <>
                  <SummaryRow label="Scholarship aid" values={aid} best={bestAid} cur={cur} tone="accent" />
                  <SummaryRow label="After aid / year" values={netTotals} best={bestNet} cur={cur} strong />
                </>
              )}
              <SummaryRow label="Monthly living" values={monthly} best={bestMonthly} cur={cur} />
            </tbody>
          </table>
        </div>
        <p className="px-4 py-2.5 text-[11px] text-muted sm:px-5">
          <span className="font-medium text-primary">Teal</span> marks the best value in each row.
        </p>
      </motion.section>
    </AnimatePresence>
  );
}

function SummaryRow({
  label,
  values,
  best,
  cur,
  strong,
  tone,
}: {
  label: string;
  values: number[];
  best: number;
  cur: string;
  strong?: boolean;
  tone?: "accent";
}) {
  const winClass = tone === "accent" ? "font-semibold text-accent" : "font-semibold text-primary";
  return (
    <tr className="border-t border-border bg-surface-2/40">
      <th scope="row" className={`px-4 py-2.5 text-left text-xs ${strong ? "font-semibold text-foreground" : "font-medium text-muted"}`}>
        {label}
      </th>
      {values.map((v, i) => (
        <td key={i} className={`figure px-3 py-2.5 ${i === best ? winClass : strong ? "font-semibold text-foreground" : "text-foreground"}`}>
          {money(v, cur)}
        </td>
      ))}
    </tr>
  );
}
