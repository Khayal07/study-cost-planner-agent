"use client";

import { useState } from "react";
import type { PlanningRequest } from "@/lib/api";

const COUNTRIES = ["", "Germany", "Netherlands", "Poland", "Hungary", "Turkey", "Czechia", "Italy"];
const CURRENCIES = ["EUR", "USD", "TRY", "PLN", "HUF", "CZK", "AZN", "GBP"];
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
  const [nationality, setNationality] = useState("");
  const [gpa, setGpa] = useState("");
  const [languageTest, setLanguageTest] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const gpaNum = gpa.trim() ? Number(gpa) : null;
    onSubmit({
      country: country || null,
      field,
      budget_amount: budget,
      budget_currency: budgetCurrency,
      report_currency: reportCurrency,
      lifestyle,
      max_results: 8,
      nationality: nationality.trim() || null,
      gpa: gpaNum != null && !Number.isNaN(gpaNum) ? gpaNum : null,
      language_test: languageTest.trim() || null,
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

        {/* Optional scholarship-eligibility inputs */}
        <details className="rounded-xl border border-border bg-surface-2/50">
          <summary className="cursor-pointer select-none px-4 py-2.5 text-xs font-medium text-muted hover:text-foreground">
            🎓 Scholarship eligibility <span className="text-muted">(optional)</span>
          </summary>
          <div className="space-y-4 border-t border-border p-4">
            <div>
              <label htmlFor="nationality" className="field-label">Nationality</label>
              <input
                id="nationality"
                className="input"
                placeholder="e.g. Azerbaijan"
                value={nationality}
                onChange={(e) => setNationality(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="gpa" className="field-label">GPA (0–4)</label>
                <input
                  id="gpa"
                  type="number"
                  className="input figure"
                  placeholder="3.5"
                  min={0}
                  max={4}
                  step={0.1}
                  value={gpa}
                  onChange={(e) => setGpa(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="languageTest" className="field-label">Language test</label>
                <input
                  id="languageTest"
                  className="input"
                  placeholder="IELTS 7.0"
                  value={languageTest}
                  onChange={(e) => setLanguageTest(e.target.value)}
                />
              </div>
            </div>
            <p className="text-[11px] text-muted">
              Used only to estimate which scholarships you may qualify for. Leave blank to skip.
            </p>
          </div>
        </details>

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
