"use client";

import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "@/lib/api";

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch((e) => setError(String(e)));
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-6 py-20">
      <p className="mb-3 text-sm font-medium uppercase tracking-widest text-brand">
        Study Cost Planning Agent
      </p>
      <h1 className="text-4xl font-bold leading-tight text-ink">
        Plan the <span className="text-brand">total real cost</span> of studying abroad.
      </h1>
      <p className="mt-4 max-w-2xl text-lg text-muted">
        Tuition is only part of the story. This multi-agent planner adds living costs,
        insurance, visa, transport and hidden expenses — every figure grounded in a
        cited source, never invented.
      </p>

      <div className="mt-10 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-muted">Backend status</h2>
        {error && <p className="mt-2 text-red-600">Cannot reach backend: {error}</p>}
        {!error && !health && <p className="mt-2 text-muted">Checking…</p>}
        {health && (
          <ul className="mt-2 space-y-1 text-sm">
            <li>
              <span className="text-muted">Service:</span>{" "}
              <span className="font-medium">{health.service}</span>{" "}
              <span className="ml-1 rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                {health.status}
              </span>
            </li>
            <li>
              <span className="text-muted">Report currency:</span>{" "}
              <span className="font-medium">{health.report_currency}</span>
            </li>
            <li>
              <span className="text-muted">LLM (chat) enabled:</span>{" "}
              <span className="font-medium">{health.llm_enabled ? "yes" : "no — set OPENROUTER_API_KEY"}</span>
            </li>
          </ul>
        )}
      </div>

      <p className="mt-8 text-sm text-muted">
        Phase 0 scaffold. Budget form, chat and reports land in the next phases.
      </p>
    </main>
  );
}
