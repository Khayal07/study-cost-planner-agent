"use client";

import { useState } from "react";
import { postPlan, type PlanningRequest, type PlanResult } from "@/lib/api";
import { BudgetForm } from "@/components/BudgetForm";
import { PlanResults } from "@/components/PlanResults";
import { ChatPanel } from "@/components/ChatPanel";
import { Navbar } from "@/components/Navbar";
import { Hero } from "@/components/Hero";
import { Footer } from "@/components/Footer";
import { ResultsSkeleton } from "@/components/Skeletons";
import { ApplicationsTracker } from "@/components/ApplicationsTracker";

type Tab = "form" | "chat" | "applications";

const TABS: { id: Tab; label: string; hint: string }[] = [
  { id: "form", label: "Budget form", hint: "Structured inputs" },
  { id: "chat", label: "Chat", hint: "Ask in plain language" },
  { id: "applications", label: "Applications", hint: "Track scholarships" },
];

export default function Home() {
  const [tab, setTab] = useState<Tab>("form");
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
    } catch {
      setError("We couldn't reach the planning service. Check the backend is running and try again.");
      setPlan(null);
    } finally {
      setLoading(false);
    }
  }

  const reportCurrency = request?.report_currency ?? "EUR";

  return (
    <>
      <Navbar />
      <Hero />

      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        {/* Segmented tab control */}
        <div
          role="tablist"
          aria-label="Planning mode"
          className="mb-8 inline-grid grid-cols-3 gap-1 rounded-2xl border border-border bg-surface-2 p-1 shadow-xs"
        >
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={`relative rounded-xl px-4 py-2 text-sm font-medium transition-all sm:px-6 ${
                tab === t.id
                  ? "bg-surface text-foreground shadow-sm"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {t.label}
              <span className="ml-2 hidden text-[11px] font-normal text-muted sm:inline">
                {t.hint}
              </span>
            </button>
          ))}
        </div>

        {tab === "form" ? (
          <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
            <div className="lg:sticky lg:top-24 lg:self-start">
              <BudgetForm onSubmit={handlePlan} loading={loading} />
            </div>
            <div className="min-w-0">
              {loading ? (
                <ResultsSkeleton />
              ) : error ? (
                <ErrorState message={error} />
              ) : plan ? (
                <div className="animate-fade-in">
                  <PlanResults plan={plan} request={request!} />
                </div>
              ) : (
                <EmptyState />
              )}
            </div>
          </div>
        ) : tab === "chat" ? (
          <div className="mx-auto max-w-5xl">
            <ChatPanel reportCurrency={reportCurrency} />
          </div>
        ) : (
          <div className="mx-auto max-w-3xl">
            <ApplicationsTracker />
          </div>
        )}
      </main>

      <Footer />
    </>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface/40 p-10 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl border border-border bg-surface text-primary shadow-sm">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 3v18h18" />
          <rect x="7" y="12" width="3" height="6" rx="1" />
          <rect x="12" y="8" width="3" height="10" rx="1" />
          <rect x="17" y="5" width="3" height="13" rx="1" />
        </svg>
      </div>
      <h3 className="mt-4 font-display text-lg font-semibold">Your cost comparison appears here</h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted">
        Set a budget and lifestyle on the left, then build a plan to see ranked options,
        scenarios, charts and a source for every figure.
      </p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-2xl border border-danger/30 bg-danger/5 p-10 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl border border-danger/30 bg-surface text-danger shadow-sm">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 9v4M12 17h.01" />
          <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        </svg>
      </div>
      <h3 className="mt-4 font-display text-lg font-semibold">Something went wrong</h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted">{message}</p>
    </div>
  );
}
