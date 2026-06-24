"use client";

import { useState } from "react";
import type { PlanningRequest } from "@/lib/api";

const COUNTRIES = ["", "Germany", "Netherlands", "Poland", "Hungary", "Turkey"];
const CURRENCIES = ["EUR", "USD", "TRY", "PLN", "AZN", "GBP"];
const LIFESTYLES: { id: string; label: string }[] = [
  { id: "frugal", label: "Frugal" },
  { id: "moderate", label: "Moderate" },
  { id: "comfortable", label: "Comfortable" },
];

export function BudgetForm({
  onSubmit,
  loading,
}: {
  onSubmit: (req: PlanningRequest) => void;
  loading: boolean;
}) {
  const [country, setCountry] = useState("");
  const [field, setField] = useState("Computer Science");
  const [budget, setBudget] = useState(10000);
  const [budgetCurrency, setBudgetCurrency] = useState("EUR");
  const [reportCurrency, setReportCurrency] = useState("EUR");
  const [lifestyle, setLifestyle] = useState("moderate");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      country: country || null,
      field,
      budget_amount: budget,
      budget_currency: budgetCurrency,
      report_currency: reportCurrency,
      lifestyle,
      max_results: 8,
    });
  }

  return (
    <form onSubmit={submit} className="card overflow-hidden">
      <div className="flex items-center gap-3 border-b border-border bg-surface-2/60 px-5 py-4">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary-weak text-primary">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 6h18M3 12h18M3 18h12" />
          </svg>
        </span>
        <div>
          <h2 className="font-display text-base font-semibold leading-none">Build a cost plan</h2>
          <p className="mt-1 text-xs text-muted">Tune your budget and lifestyle</p>
        </div>
      </div>

      <div className="space-y-4 p-5">
        <div>
          <label htmlFor="field" className="field-label">Field of study</label>
          <input id="field" className="input" value={field} onChange={(e) => setField(e.target.value)} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="country" className="field-label">Country</label>
            <select id="country" className="input" value={country} onChange={(e) => setCountry(e.target.value)}>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>{c || "All countries"}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="budget" className="field-label">Yearly budget</label>
            <input
              id="budget"
              type="number"
              className="input figure"
              value={budget}
              min={0}
              step={500}
              onChange={(e) => setBudget(Number(e.target.value))}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="budgetCurrency" className="field-label">Budget currency</label>
            <select id="budgetCurrency" className="input" value={budgetCurrency} onChange={(e) => setBudgetCurrency(e.target.value)}>
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="reportCurrency" className="field-label">Show results in</label>
            <select id="reportCurrency" className="input" value={reportCurrency} onChange={(e) => setReportCurrency(e.target.value)}>
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Lifestyle segmented control */}
        <div>
          <label className="field-label">Lifestyle</label>
          <div role="radiogroup" aria-label="Lifestyle" className="grid grid-cols-3 gap-1 rounded-xl border border-border bg-surface-2 p-1">
            {LIFESTYLES.map((l) => (
              <button
                key={l.id}
                type="button"
                role="radio"
                aria-checked={lifestyle === l.id}
                onClick={() => setLifestyle(l.id)}
                className={`rounded-lg px-2 py-1.5 text-xs font-medium transition-all ${
                  lifestyle === l.id
                    ? "bg-surface text-foreground shadow-sm"
                    : "text-muted hover:text-foreground"
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>

        <button type="submit" disabled={loading} className="btn-primary mt-1 w-full">
          {loading ? (
            <>
              <Spinner /> Planning…
            </>
          ) : (
            <>
              Build cost plan
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </>
          )}
        </button>
      </div>
    </form>
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
