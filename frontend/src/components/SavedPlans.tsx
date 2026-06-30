"use client";

import { useEffect, useState } from "react";
import { listSavedPlans, deleteSavedPlan, type SavedPlanOut } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { ApplicationsSkeleton } from "./Skeletons";

export function SavedPlans() {
  const { isAuthed, openAuth } = useAuth();
  const { t } = useI18n();
  const [plans, setPlans] = useState<SavedPlanOut[] | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthed) {
      setPlans([]);
      return;
    }
    listSavedPlans()
      .then(setPlans)
      .catch(() => setPlans([]));
  }, [isAuthed]);

  if (!isAuthed) {
    return (
      <div className="card flex min-h-[280px] flex-col items-center justify-center p-10 text-center">
        <h3 className="font-display text-lg font-semibold">{t("saved.signinTitle")}</h3>
        <p className="mt-1.5 max-w-sm text-sm text-muted">
          {t("saved.signinBody")}
        </p>
        <button onClick={openAuth} className="btn-primary mt-4">{t("saved.signinBtn")}</button>
      </div>
    );
  }

  if (plans === null) return <ApplicationsSkeleton />;

  if (plans.length === 0) {
    return (
      <div className="card flex min-h-[280px] flex-col items-center justify-center p-10 text-center">
        <h3 className="font-display text-lg font-semibold">{t("saved.emptyTitle")}</h3>
        <p className="mt-1.5 max-w-sm text-sm text-muted">
          {t("saved.emptyBodyA")} <span className="font-medium text-foreground">{t("saved.shareAction")}</span> {t("saved.emptyBodyB")}
        </p>
      </div>
    );
  }

  async function remove(id: number) {
    setPlans((prev) => prev?.filter((p) => p.id !== id) ?? null);
    try {
      await deleteSavedPlan(id);
    } catch {
      /* re-fetch on failure to stay consistent */
      listSavedPlans().then(setPlans).catch(() => {});
    }
  }

  async function copy(publicId: string) {
    const url = `${window.location.origin}/p/${publicId}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(publicId);
      setTimeout(() => setCopiedId((c) => (c === publicId ? null : c)), 1500);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="space-y-3">
      <h2 className="font-display text-xl font-semibold tracking-tight">{t("saved.heading")}</h2>
      {plans.map((p) => (
        <div key={p.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
          <div className="min-w-0">
            <a href={`/p/${p.public_id}`} className="text-sm font-semibold hover:text-primary">{p.title}</a>
            <p className="mt-0.5 text-xs text-muted">
              <span className="figure">{p.request.budget_amount.toLocaleString()} {p.request.budget_currency}</span>
              {" · "}{p.request.lifestyle}
              {" · "}{new Date(p.created_at).toLocaleDateString()}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <a href={`/p/${p.public_id}`} className="btn-ghost px-3 py-1.5 text-xs">{t("saved.open")}</a>
            <button onClick={() => copy(p.public_id)} className="btn-ghost px-3 py-1.5 text-xs">
              {copiedId === p.public_id ? t("saved.copied") : t("saved.copy")}
            </button>
            <button
              onClick={() => remove(p.id)}
              aria-label={t("saved.delete")}
              className="rounded-lg border border-border bg-surface px-2 py-1.5 text-muted transition-colors hover:border-danger/40 hover:text-danger"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
              </svg>
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
