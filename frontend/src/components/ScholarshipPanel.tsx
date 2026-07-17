"use client";

import { useState } from "react";
import type {
  CandidatePlan,
  LiveScholarship,
  ScholarshipEligibility,
  ScholarshipMatch,
} from "@/lib/api";
import { searchLiveScholarships } from "@/lib/api";
import { CitationChip } from "./CitationChip";

const ELIGIBILITY: Record<
  ScholarshipEligibility,
  { label: string; cls: string; dot: string }
> = {
  eligible: { label: "Eligible", cls: "bg-primary-weak text-primary", dot: "bg-primary" },
  likely: { label: "Likely", cls: "bg-accent-weak text-accent", dot: "bg-accent" },
  unknown: { label: "Needs detail", cls: "bg-surface-2 text-muted", dot: "bg-muted" },
  ineligible: { label: "Not eligible", cls: "bg-surface-2 text-muted line-through", dot: "bg-border" },
};

const ORDER: ScholarshipEligibility[] = ["eligible", "likely", "unknown", "ineligible"];

/** Compact 0–100 fit meter — teal when strong, amber mid, muted/low when weak. */
function MatchScore({ score, eligible }: { score: number; eligible: boolean }) {
  const tone = !eligible ? "bg-border" : score >= 75 ? "bg-primary" : score >= 50 ? "bg-accent" : "bg-muted";
  const text = !eligible ? "text-muted" : score >= 75 ? "text-primary" : score >= 50 ? "text-accent" : "text-muted";
  return (
    <div className="flex items-center gap-1.5" title={`Match score: ${score}/100`}>
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-2">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${score}%` }} />
      </div>
      <span className={`figure text-[11px] font-semibold ${text}`}>{score}</span>
    </div>
  );
}

function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${Math.round(amount).toLocaleString()}`;
  }
}

function ScholarshipRow({
  m,
  currency,
  onTrack,
  tracked,
}: {
  m: ScholarshipMatch;
  currency: string;
  onTrack?: (m: ScholarshipMatch) => void;
  tracked?: boolean;
}) {
  const e = ELIGIBILITY[m.eligibility] ?? ELIGIBILITY.unknown;
  const muted = m.eligibility === "ineligible";
  const deadlineSoon = m.days_until_deadline != null && m.days_until_deadline >= 0 && m.days_until_deadline <= 30;
  return (
    <div className={`rounded-xl border border-border p-3 ${muted ? "opacity-60" : "bg-surface"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{m.name}</p>
          <p className="truncate text-xs text-muted">{m.provider}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${e.cls}`}>
            <span className={`mr-1 inline-block h-1.5 w-1.5 rounded-full align-middle ${e.dot}`} />
            {e.label}
          </span>
          <MatchScore score={m.match_score} eligible={m.eligibility !== "ineligible"} />
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <span className="text-muted">
          Worth{" "}
          <span className="figure font-semibold text-foreground">
            {m.estimated_value > 0 ? `~${money(m.estimated_value, currency)}/yr` : "varies"}
          </span>
        </span>
        <span className="chip text-[11px]">{m.coverage_type.replace(/_/g, " ")}</span>
        {m.deadline && (
          <span className={deadlineSoon ? "font-medium text-accent" : "text-muted"}>
            Deadline {m.deadline}
            {m.days_until_deadline != null && m.days_until_deadline >= 0
              ? ` · ${m.days_until_deadline}d left`
              : ""}
          </span>
        )}
        {m.renewable && <span className="text-muted">Renewable</span>}
      </div>

      {m.reasons.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-[11px] text-muted">
          {m.reasons.slice(0, 4).map((r, i) => (
            <li key={i}>• {r}</li>
          ))}
        </ul>
      )}

      {m.tips.length > 0 && (
        <div className="mt-2 rounded-lg border border-accent/30 bg-accent-weak/50 p-2">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold text-accent">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1h6c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2Z" />
            </svg>
            Improve your odds
          </p>
          <ul className="mt-1 space-y-0.5 text-[11px] text-foreground/80">
            {m.tips.map((t, i) => (
              <li key={i}>• {t}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-2 flex items-center justify-between gap-2">
        <CitationChip citation={m.citation} />
        <div className="flex items-center gap-2">
          {onTrack && m.eligibility !== "ineligible" && (
            <button
              onClick={() => onTrack(m)}
              disabled={tracked}
              className={tracked ? "chip bg-primary-weak text-primary" : "btn-ghost px-2.5 py-1 text-xs"}
            >
              {tracked ? "Tracked ✓" : "+ Track"}
            </button>
          )}
          {m.application_url && (
            <a
              href={m.application_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost px-2.5 py-1 text-xs"
            >
              Apply ↗
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

/** On-demand live web search for scholarships. Explicit button → one paid API
 *  call (cached 24h server-side), results shown separately from the dataset.
 *  Selected awards preview a reduced total and can be folded into the PDF. */
function LiveScholarshipSearch({
  country,
  field,
  degreeLevel,
  currency,
  totalAnnual,
  onExportLive,
  onTrackLive,
  trackedLive,
}: {
  country: string;
  field: string;
  degreeLevel: string | null;
  currency: string;
  totalAnnual: number;
  onExportLive?: (selected: LiveScholarship[]) => Promise<void> | void;
  onTrackLive?: (r: LiveScholarship) => void;
  trackedLive?: Set<string>;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<LiveScholarship[] | null>(null);
  const [cached, setCached] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [exporting, setExporting] = useState(false);

  const canSearch = country.trim().length > 1 && field.trim().length > 1;

  async function run() {
    setLoading(true);
    setError(null);
    setSelected(new Set());
    try {
      const resp = await searchLiveScholarships(country, field, degreeLevel, currency);
      setResults(resp.results);
      setCached(resp.cached);
      setNote(resp.note);
    } catch {
      setError("Live search failed. Please try again in a moment.");
    } finally {
      setLoading(false);
    }
  }

  function toggle(i: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  const selectedList = results ? [...selected].map((i) => results[i]).filter(Boolean) : [];
  const selectedValue = selectedList.reduce((sum, r) => sum + (r.annual_value ?? 0), 0);
  const adjustedTotal = Math.max(0, totalAnnual - selectedValue);

  async function generate() {
    if (!onExportLive) return;
    setExporting(true);
    try {
      await onExportLive(selectedList);
    } catch {
      setError("Could not generate the PDF. Please try again.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="mt-4 border-t border-border pt-4">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-sm font-semibold">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent" aria-hidden="true">
              <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
            </svg>
            Live scholarships from the web
          </p>
          <p className="truncate text-[11px] text-muted">
            AI-fetched for {field} in {country} — verify each at its source.
          </p>
        </div>
        <button
          onClick={run}
          disabled={loading || !canSearch}
          className="btn-primary shrink-0 px-3 py-1.5 text-xs disabled:opacity-50"
        >
          {loading ? "Searching…" : results ? "Search again" : "Find live scholarships 🔍"}
        </button>
      </div>

      {error && <p className="mt-3 text-xs text-red-500">{error}</p>}

      {results && (
        <div className="mt-3">
          {cached && (
            <span className="chip mb-2 inline-block text-[11px]">Cached (updated within 24h)</span>
          )}
          {results.length === 0 ? (
            <p className="text-xs text-muted">{note ?? "No live scholarships found."}</p>
          ) : (
            <div className="space-y-2">
              <p className="text-[11px] text-muted">
                Tick the awards you may pursue to preview your total after aid, then generate a PDF.
              </p>
              {results.map((r, i) => {
                const isSel = selected.has(i);
                return (
                  <label
                    key={i}
                    className={`block cursor-pointer rounded-xl border p-3 transition ${
                      isSel ? "border-primary ring-1 ring-primary/40 bg-primary-weak/20" : "border-border bg-surface"
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <input
                        type="checkbox"
                        checked={isSel}
                        onChange={() => toggle(i)}
                        className="mt-1 h-4 w-4 shrink-0 accent-[var(--primary)]"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold">{r.name}</p>
                            {r.provider && <p className="truncate text-xs text-muted">{r.provider}</p>}
                          </div>
                          <span className="shrink-0 rounded-full bg-accent-weak px-2 py-0.5 text-[11px] font-semibold text-accent">
                            <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-accent align-middle" />
                            Web
                          </span>
                        </div>

                        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                          <span className="text-muted">
                            Worth{" "}
                            <span className="figure font-semibold text-foreground">
                              {r.annual_value != null
                                ? `~${money(r.annual_value, currency)}/yr`
                                : r.amount ?? "varies"}
                            </span>
                          </span>
                          {r.coverage_type && <span className="chip text-[11px]">{r.coverage_type}</span>}
                          {r.deadline && <span className="text-muted">Deadline {r.deadline}</span>}
                        </div>

                        {r.eligibility && (
                          <ul className="mt-2 space-y-0.5 text-[11px] text-muted">
                            <li>• {r.eligibility}</li>
                            {r.annual_value == null && (
                              <li>• Value not estimated — won&apos;t change the total</li>
                            )}
                          </ul>
                        )}

                        <div className="mt-2 flex items-center justify-between gap-2">
                          <span className="text-[11px] text-muted">AI-found · verify at source</span>
                          <div className="flex items-center gap-2">
                            {onTrackLive && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  // Inside a <label>, so stop the click from toggling the checkbox.
                                  e.preventDefault();
                                  e.stopPropagation();
                                  onTrackLive(r);
                                }}
                                disabled={trackedLive?.has(r.name)}
                                className={
                                  trackedLive?.has(r.name)
                                    ? "chip bg-primary-weak text-primary"
                                    : "btn-ghost px-2.5 py-1 text-xs"
                                }
                              >
                                {trackedLive?.has(r.name) ? "Tracked ✓" : "+ Track"}
                              </button>
                            )}
                            {r.official_url && (
                              <a
                                href={r.official_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="btn-ghost px-2.5 py-1 text-xs"
                              >
                                Apply ↗
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </label>
                );
              })}

              {selected.size > 0 && (
                <div className="rounded-xl border border-primary/30 bg-primary-weak/40 p-3 text-sm">
                  Applying {selected.size} selected award{selected.size > 1 ? "s" : ""} (~
                  <span className="figure font-semibold">{money(selectedValue, currency)}</span>) lowers
                  this option&apos;s total from{" "}
                  <span className="figure text-muted line-through">{money(totalAnnual, currency)}</span> to{" "}
                  <span className="figure font-semibold text-primary">
                    {money(adjustedTotal, currency)}/yr
                  </span>
                  .
                  {onExportLive && (
                    <div className="mt-2.5">
                      <button
                        onClick={generate}
                        disabled={exporting}
                        className="btn-primary px-3 py-1.5 text-xs disabled:opacity-50"
                      >
                        {exporting ? "Generating…" : "Generate PDF with selected 📄"}
                      </button>
                    </div>
                  )}
                </div>
              )}

              <p className="text-[11px] text-muted">
                These results are gathered live by AI and may be incomplete or out of date.
                Always confirm terms and deadlines at the official source before applying.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ScholarshipPanel({
  candidate,
  onTrack,
  trackedIds,
  onTrackLive,
  trackedLive,
  onExportLive,
}: {
  candidate: CandidatePlan;
  onTrack?: (m: ScholarshipMatch, candidate: CandidatePlan) => void;
  trackedIds?: Set<number>;
  // When provided, a web-found award can be saved to the tracker (deadline left unset).
  onTrackLive?: (r: LiveScholarship, candidate: CandidatePlan) => void;
  trackedLive?: Set<string>;
  // When provided, selected live scholarships can be folded into a PDF for this candidate.
  onExportLive?: (selected: LiveScholarship[], candidate: CandidatePlan) => Promise<void> | void;
}) {
  const currency = candidate.report_currency;
  const all = [...candidate.scholarships].sort(
    (a, b) => ORDER.indexOf(a.eligibility) - ORDER.indexOf(b.eligibility),
  );
  const applicable = all.filter((m) => m.eligibility !== "ineligible");
  const hasNet =
    candidate.net_total_annual != null && candidate.total_scholarship_value > 0;
  // Unique, actionable steps to unlock more awards (deduped across applicable matches).
  const improveTips = Array.from(new Set(applicable.flatMap((m) => m.tips)));

  if (all.length === 0) {
    return (
      <div className="card p-5">
        <h3 className="font-display text-base font-semibold">Scholarships</h3>
        <p className="mt-2 text-sm text-muted">
          No scholarships in the dataset match this option yet. Add your nationality, GPA and
          language test above to refine eligibility.
        </p>
        <LiveScholarshipSearch
          country={candidate.country_name}
          field={candidate.field}
          degreeLevel={candidate.degree_level}
          currency={currency}
          totalAnnual={candidate.total_annual}
          onTrackLive={onTrackLive ? (r) => onTrackLive(r, candidate) : undefined}
          trackedLive={trackedLive}
          onExportLive={onExportLive ? (sel) => onExportLive(sel, candidate) : undefined}
        />
      </div>
    );
  }

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 font-display text-base font-semibold">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary" aria-hidden="true">
            <path d="M22 10 12 5 2 10l10 5 10-5Z" /><path d="M6 12v5c0 1 2.5 2.5 6 2.5s6-1.5 6-2.5v-5" />
          </svg>
          Scholarships{" "}
          <span className="text-sm font-normal text-muted">
            ({applicable.length} you may qualify for)
          </span>
        </h3>
      </div>

      {hasNet && (
        <div className="mt-3 rounded-xl border border-primary/30 bg-primary-weak/40 p-3 text-sm">
          Applying the best award you may qualify for (~
          <span className="figure font-semibold">
            {money(candidate.total_scholarship_value, currency)}
          </span>
          ) lowers your estimated total from{" "}
          <span className="figure text-muted line-through">
            {money(candidate.total_annual, currency)}
          </span>{" "}
          to{" "}
          <span className="figure font-semibold text-primary">
            {money(candidate.net_total_annual as number, currency)}/yr
          </span>
          .
        </div>
      )}

      {improveTips.length > 0 && (
        <div className="mt-3 rounded-xl border border-accent/30 bg-accent-weak/40 p-3">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-accent">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1h6c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2Z" />
            </svg>
            Improve your eligibility
          </p>
          <ul className="mt-1.5 space-y-1 text-xs text-foreground/85">
            {improveTips.map((t, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                <span>{t}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-muted">Add these in the form&apos;s eligibility section, then rebuild your plan.</p>
        </div>
      )}

      <div className="mt-3 space-y-2">
        {all.map((m) => (
          <ScholarshipRow
            key={m.scholarship_id}
            m={m}
            currency={currency}
            onTrack={onTrack ? (mm) => onTrack(mm, candidate) : undefined}
            tracked={trackedIds?.has(m.scholarship_id)}
          />
        ))}
      </div>

      <p className="mt-3 text-[11px] text-muted">
        Eligibility is an automated read from the profile you provided. Confirm each award&apos;s
        terms at its cited source before applying.
      </p>

      <LiveScholarshipSearch
        country={candidate.country_name}
        field={candidate.field}
        degreeLevel={candidate.degree_level}
        currency={currency}
        totalAnnual={candidate.total_annual}
        onTrackLive={onTrackLive ? (r) => onTrackLive(r, candidate) : undefined}
        trackedLive={trackedLive}
        onExportLive={onExportLive ? (sel) => onExportLive(sel, candidate) : undefined}
      />
    </div>
  );
}
