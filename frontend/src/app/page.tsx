"use client";

import { useState } from "react";
import { postPlan, type PlanningRequest, type PlanResult } from "@/lib/api";
import { BudgetForm } from "@/components/BudgetForm";
import { PlanResults } from "@/components/PlanResults";
import { ChatPanel } from "@/components/ChatPanel";

export default function Home() {
  const [tab, setTab] = useState<"form" | "chat">("form");
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [request, setRequest] = useState<PlanningRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handlePlan(req: PlanningRequest) {
    setLoading(true);
    setError(null);
    setRequest(req);
    try {
      setPlan(await postPlan(req));
    } catch (e) {
      setError(String(e));
      setPlan(null);
    } finally {
      setLoading(false);
    }
  }

  const reportCurrency = request?.report_currency ?? "EUR";

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-brand">
          Study Cost Planning Agent
        </p>
        <h1 className="mt-1 text-3xl font-bold">
          The <span className="text-brand">total real cost</span> of studying abroad
        </h1>
        <p className="mt-2 max-w-2xl text-muted">
          Tuition, living, insurance, visa, transport and hidden costs — every figure
          grounded in a cited source.
        </p>
      </header>

      <div className="mb-6 inline-flex rounded-lg border border-slate-200 bg-white p-1">
        {(["form", "chat"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium capitalize ${
              tab === t ? "bg-brand text-white" : "text-muted hover:text-ink"
            }`}
          >
            {t === "form" ? "Budget form" : "Chat"}
          </button>
        ))}
      </div>

      {tab === "form" ? (
        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <div>
            <BudgetForm onSubmit={handlePlan} loading={loading} />
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          </div>
          <div>
            {plan ? (
              <PlanResults plan={plan} request={request!} />
            ) : (
              <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-slate-300 p-10 text-center text-muted">
                Fill the form to see ranked options, charts, scenarios and citations.
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="max-w-3xl">
          <ChatPanel reportCurrency={reportCurrency} />
        </div>
      )}
    </main>
  );
}
