"use client";

import { useState } from "react";
import type { PlanningRequest } from "@/lib/api";

const COUNTRIES = ["", "Germany", "Netherlands", "Poland", "Hungary", "Turkey"];
const CURRENCIES = ["EUR", "USD", "TRY", "PLN", "AZN", "GBP"];
const LIFESTYLES = ["frugal", "moderate", "comfortable"];

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

  const labelCls = "block text-xs font-medium text-muted mb-1";
  const inputCls =
    "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none";

  return (
    <form onSubmit={submit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-base font-semibold">Budget plan</h2>
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className={labelCls}>Field of study</label>
          <input className={inputCls} value={field} onChange={(e) => setField(e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Country (optional)</label>
          <select className={inputCls} value={country} onChange={(e) => setCountry(e.target.value)}>
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>{c || "All countries"}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Lifestyle</label>
          <select className={inputCls} value={lifestyle} onChange={(e) => setLifestyle(e.target.value)}>
            {LIFESTYLES.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Yearly budget</label>
          <input
            type="number"
            className={inputCls}
            value={budget}
            min={0}
            onChange={(e) => setBudget(Number(e.target.value))}
          />
        </div>
        <div>
          <label className={labelCls}>Budget currency</label>
          <select className={inputCls} value={budgetCurrency} onChange={(e) => setBudgetCurrency(e.target.value)}>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div className="col-span-2">
          <label className={labelCls}>Report currency</label>
          <select className={inputCls} value={reportCurrency} onChange={(e) => setReportCurrency(e.target.value)}>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>
      <button
        type="submit"
        disabled={loading}
        className="mt-5 w-full rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-50"
      >
        {loading ? "Planning…" : "Build cost plan"}
      </button>
    </form>
  );
}
