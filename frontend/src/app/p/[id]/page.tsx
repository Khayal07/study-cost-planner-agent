"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getSharedPlan, type SavedPlanDetail } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { PlanResults } from "@/components/PlanResults";
import { ResultsSkeleton } from "@/components/Skeletons";

export default function SharedPlanPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [data, setData] = useState<SavedPlanDetail | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!id) return;
    setError(false);
    getSharedPlan(id)
      .then(setData)
      .catch(() => setError(true));
  }, [id]);

  return (
    <>
      <Navbar />
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <a href="/" className="mb-6 inline-flex items-center gap-1.5 text-sm font-medium text-muted transition-colors hover:text-foreground">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M19 12H5M11 18l-6-6 6-6" />
          </svg>
          Build your own plan
        </a>

        {error ? (
          <div className="card flex min-h-[300px] flex-col items-center justify-center p-10 text-center">
            <h1 className="font-display text-lg font-semibold">This shared plan isn&apos;t available</h1>
            <p className="mt-1.5 max-w-sm text-sm text-muted">
              The link may be wrong or the plan was removed. You can build a fresh one from the homepage.
            </p>
          </div>
        ) : !data ? (
          <ResultsSkeleton />
        ) : (
          <>
            <div className="mb-6">
              <span className="chip border border-primary/30 bg-primary-weak text-primary">Shared plan</span>
              <h1 className="mt-3 font-display text-2xl font-semibold tracking-tight">{data.title}</h1>
              <p className="mt-1 text-sm text-muted">
                Figures are recomputed live from current sourced data.
              </p>
            </div>
            <PlanResults plan={data.plan} request={data.request} />
          </>
        )}
      </main>
      <Footer />
    </>
  );
}
