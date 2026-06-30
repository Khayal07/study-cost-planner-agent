"use client";

import { useEffect, useState } from "react";
import {
  deleteApplication,
  listApplications,
  toggleDocument,
  updateApplication,
  type ApplicationOut,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { ApplicationsSkeleton } from "./Skeletons";
import { DeadlineCalendar } from "./DeadlineCalendar";
import { downloadIcs } from "@/lib/ics";

const STATUSES = ["planned", "in_progress", "submitted", "accepted", "rejected"] as const;
const STATUS_CLS: Record<string, string> = {
  planned: "bg-surface-2 text-muted",
  in_progress: "bg-accent-weak text-accent",
  submitted: "bg-primary-weak text-primary",
  accepted: "bg-primary text-primary-fg",
  rejected: "bg-danger/10 text-danger",
};

function money(amount: number | null, currency: string | null): string {
  if (amount == null) return "—";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency ?? "EUR",
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency ?? ""} ${Math.round(amount).toLocaleString()}`;
  }
}

function byDeadline(a: ApplicationOut, b: ApplicationOut): number {
  const da = a.days_until_deadline ?? 1e9;
  const db = b.days_until_deadline ?? 1e9;
  return da - db;
}

export function ApplicationsTracker() {
  const { isAuthed, ready, openAuth } = useAuth();
  const { t } = useI18n();
  const [apps, setApps] = useState<ApplicationOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"list" | "calendar">("list");

  useEffect(() => {
    if (!ready || !isAuthed) return;
    setLoading(true);
    listApplications()
      .then(setApps)
      .catch(() => setError(t("app.errLoad")))
      .finally(() => setLoading(false));
  }, [ready, isAuthed]);

  function replace(updated: ApplicationOut) {
    setApps((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  }

  async function onToggleDoc(appId: number, docId: number, done: boolean) {
    replace({
      ...apps.find((a) => a.id === appId)!,
      documents: apps
        .find((a) => a.id === appId)!
        .documents.map((d) => (d.id === docId ? { ...d, done } : d)),
    });
    try {
      replace(await toggleDocument(appId, docId, done));
    } catch {
      /* best-effort; reload on next mount */
    }
  }

  async function onStatus(appId: number, status: string) {
    try {
      replace(await updateApplication(appId, { status }));
    } catch {
      setError(t("app.errStatus"));
    }
  }

  async function onDelete(appId: number) {
    setApps((prev) => prev.filter((a) => a.id !== appId));
    try {
      await deleteApplication(appId);
    } catch {
      /* ignore */
    }
  }

  if (ready && !isAuthed) {
    return (
      <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface/40 p-10 text-center">
        <h3 className="font-display text-lg font-semibold">{t("app.signinTitle")}</h3>
        <p className="mt-1.5 max-w-sm text-sm text-muted">
          {t("app.signinBody")}
        </p>
        <button onClick={openAuth} className="btn-primary mt-4">{t("app.signinBtn")}</button>
      </div>
    );
  }

  if (loading) return <ApplicationsSkeleton />;
  if (error) return <div className="card p-8 text-center text-sm text-danger">{error}</div>;

  if (apps.length === 0) {
    return (
      <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface/40 p-10 text-center">
        <h3 className="font-display text-lg font-semibold">{t("app.emptyTitle")}</h3>
        <p className="mt-1.5 max-w-sm text-sm text-muted">
          {t("app.emptyBodyA")}{" "}
          <span className="font-medium text-foreground">{t("app.track")}</span> {t("app.emptyBodyB")}
        </p>
      </div>
    );
  }

  const sorted = [...apps].sort(byDeadline);
  const active = sorted.filter((a) => !["submitted", "accepted", "rejected"].includes(a.status));
  const thisWeek = active.filter(
    (a) => a.days_until_deadline != null && a.days_until_deadline >= 0 && a.days_until_deadline <= 14,
  );
  const hasDeadlines = apps.some((a) => a.deadline);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-display text-xl font-semibold tracking-tight">{t("app.heading")}</h2>
        <span className="chip bg-surface-2 text-muted">{apps.length} {t("app.tracked")}</span>

        <div className="ml-auto flex items-center gap-2">
          <div role="tablist" aria-label={t("app.view")} className="inline-grid grid-cols-2 gap-1 rounded-xl border border-border bg-surface-2 p-1">
            {(["list", "calendar"] as const).map((v) => (
              <button
                key={v}
                role="tab"
                aria-selected={view === v}
                onClick={() => setView(v)}
                className={`rounded-lg px-3 py-1 text-xs font-medium transition-all ${
                  view === v ? "bg-surface text-foreground shadow-sm" : "text-muted hover:text-foreground"
                }`}
              >
                {t(`app.view.${v}`)}
              </button>
            ))}
          </div>
          <button
            onClick={() => downloadIcs(apps)}
            disabled={!hasDeadlines}
            title={hasDeadlines ? t("app.exportHas") : t("app.exportNone")}
            className="btn-ghost px-3 py-1.5 text-xs disabled:pointer-events-none disabled:opacity-50"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18M12 14v4M10 16h4" />
            </svg>
            {t("app.export")}
          </button>
        </div>
      </div>

      {thisWeek.length > 0 && (
        <div className="card border-accent/30 bg-accent-weak/40 p-4">
          <div className="mb-2 text-sm font-semibold text-accent">⏰ {t("app.thisWeek")}</div>
          <ul className="space-y-1.5 text-sm">
            {thisWeek.map((a) => (
              <li key={a.id} className="flex gap-2 leading-relaxed">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <span>
                  {t("app.submit")} <b>{a.scholarship_name}</b>
                  {a.university_name ? ` (${a.university_name})` : ""} {t("app.by")} {a.deadline} —{" "}
                  {a.days_until_deadline} {t("app.daysLeft")}.
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {view === "calendar" ? (
        <DeadlineCalendar apps={apps} />
      ) : (
        <div className="space-y-3">
          {sorted.map((a) => (
            <ApplicationCard
              key={a.id}
              a={a}
              onToggleDoc={onToggleDoc}
              onStatus={onStatus}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ApplicationCard({
  a,
  onToggleDoc,
  onStatus,
  onDelete,
}: {
  a: ApplicationOut;
  onToggleDoc: (appId: number, docId: number, done: boolean) => void;
  onStatus: (appId: number, status: string) => void;
  onDelete: (appId: number) => void;
}) {
  const { t } = useI18n();
  const done = a.documents.filter((d) => d.done).length;
  const overdue = a.days_until_deadline != null && a.days_until_deadline < 0;
  const soon = a.days_until_deadline != null && a.days_until_deadline >= 0 && a.days_until_deadline <= 14;

  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{a.scholarship_name}</p>
          <p className="text-xs text-muted">
            {[a.provider, a.university_name].filter(Boolean).join(" · ") || "—"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={a.status}
            onChange={(e) => onStatus(a.id, e.target.value)}
            className={`rounded-lg border border-border px-2 py-1 text-xs font-medium ${STATUS_CLS[a.status] ?? ""}`}
            aria-label={t("app.status")}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{t(`app.st.${s}`)}</option>
            ))}
          </select>
          <button
            onClick={() => onDelete(a.id)}
            aria-label={t("app.remove")}
            className="rounded-lg p-1.5 text-muted transition-colors hover:bg-danger/10 hover:text-danger"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
            </svg>
          </button>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {a.estimated_value != null && (
          <span className="text-muted">
            {t("app.worth")} <span className="figure font-semibold text-foreground">{money(a.estimated_value, a.currency)}/yr</span>
          </span>
        )}
        {a.deadline && (
          <span className={overdue ? "font-medium text-danger" : soon ? "font-medium text-accent" : "text-muted"}>
            {t("app.deadline")} {a.deadline}
            {a.days_until_deadline != null
              ? overdue
                ? ` · ${t("app.overdue")}`
                : ` · ${a.days_until_deadline}d ${t("app.dLeft")}`
              : ""}
          </span>
        )}
        {a.application_url && (
          <a href={a.application_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
            {t("app.apply")} ↗
          </a>
        )}
      </div>

      {a.documents.length > 0 && (
        <div className="mt-3 border-t border-border pt-3">
          <div className="mb-2 flex items-center justify-between text-[11px] font-medium uppercase tracking-wide text-muted">
            <span>{t("app.documents")}</span>
            <span>{done}/{a.documents.length} {t("app.ready")}</span>
          </div>
          <div className="grid gap-1.5 sm:grid-cols-2">
            {a.documents.map((d) => (
              <label key={d.id} className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={d.done}
                  onChange={(e) => onToggleDoc(a.id, d.id, e.target.checked)}
                  className="h-4 w-4 rounded border-border accent-primary"
                />
                <span className={d.done ? "text-muted line-through" : ""}>{d.name}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
