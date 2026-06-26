import type { CandidatePlan, ScholarshipEligibility, ScholarshipMatch } from "@/lib/api";
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

function ScholarshipRow({ m, currency }: { m: ScholarshipMatch; currency: string }) {
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
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${e.cls}`}>
          <span className={`mr-1 inline-block h-1.5 w-1.5 rounded-full align-middle ${e.dot}`} />
          {e.label}
        </span>
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

      <div className="mt-2 flex items-center justify-between gap-2">
        <CitationChip citation={m.citation} />
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
  );
}

export function ScholarshipPanel({ candidate }: { candidate: CandidatePlan }) {
  const currency = candidate.report_currency;
  const all = [...candidate.scholarships].sort(
    (a, b) => ORDER.indexOf(a.eligibility) - ORDER.indexOf(b.eligibility),
  );
  const applicable = all.filter((m) => m.eligibility !== "ineligible");
  const hasNet =
    candidate.net_total_annual != null && candidate.total_scholarship_value > 0;

  if (all.length === 0) {
    return (
      <div className="card p-5">
        <h3 className="font-display text-base font-semibold">Scholarships</h3>
        <p className="mt-2 text-sm text-muted">
          No scholarships in the dataset match this option yet. Add your nationality, GPA and
          language test above to refine eligibility.
        </p>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-display text-base font-semibold">
          🎓 Scholarships{" "}
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

      <div className="mt-3 space-y-2">
        {all.map((m) => (
          <ScholarshipRow key={m.scholarship_id} m={m} currency={currency} />
        ))}
      </div>

      <p className="mt-3 text-[11px] text-muted">
        Eligibility is an automated read from the profile you provided. Confirm each award&apos;s
        terms at its cited source before applying.
      </p>
    </div>
  );
}
