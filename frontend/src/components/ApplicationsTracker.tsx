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

const STATUSES = ["planned", "in_progress", "submitted", "accepted", "rejected"] as const;
const STATUS_LABEL: Record<string, string> = {
  planned: "Planned",
  in_progress: "In progress",
  submitted: "Submitted",
  accepted: "Accepted",
  rejected: "Rejected",
};
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
  const [apps, setApps] = useState<ApplicationOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready || !isAuthed) return;
    setLoading(true);
    listApplications()
      .then(setApps)
      .catch(() => setError("Couldn't load your applications."))
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
      setError("Couldn't update status.");
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
        <h3 className="font-display text-lg font-semibold">Track your scholarship applications</h3>
        <p className="mt-1.5 max-w-sm text-sm text-muted">
          Sign in to save scholarships, manage deadlines and tick off documents as you go —
          all stored to your account.
        </p>
        <button onClick={openAuth} className="btn-primary mt-4">Sign in / Create account</button>
      </div>
    );
  }

  if (loading) return <div className="card p-8 text-center text-sm text-muted">Loading your applications…</div>;
  if (error) return <div className="card p-8 text-center text-sm text-danger">{error}</div>;

  if (apps.length === 0) {
    return (
      <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface/40 p-10 text-center">
        <h3 className="font-display text-lg font-semibold">No applications yet</h3>
        <p className="mt-1.5 max-w-sm text-sm text-muted">
          Build a plan, open a university&apos;s scholarships and tap{" "}
          <span className="font-medium text-foreground">Track</span> to add one here.
        </p>
      </div>
    );
  }

  const sorted = [...apps].sort(byDeadline);
  const active = sorted.filter((a) => !["submitted", "accepted", "rejected"].includes(a.status));
  const thisWeek = active.filter(
    (a) => a.days_until_deadline != null && a.days_until_deadline >= 0 && a.days_until_deadline <= 14,
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-display text-xl font-semibold tracking-tight">My applications</h2>
        <span className="chip bg-surface-2 text-muted">{apps.length} tracked</span>
      </div>

      {thisWeek.length > 0 && (
        <div className="card border-accent/30 bg-accent-weak/40 p-4">
          <div className="mb-2 text-sm font-semibold text-accent">⏰ This week</div>
          <ul className="space-y-1.5 text-sm">
            {thisWeek.map((a) => (
              <li key={a.id} className="flex gap-2 leading-relaxed">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <span>
                  Submit <b>{a.scholarship_name}</b>
                  {a.university_name ? ` (${a.university_name})` : ""} by {a.deadline} —{" "}
                  {a.days_until_deadline} days left.
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

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
            aria-label="Application status"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_LABEL[s]}</option>
            ))}
          </select>
          <button
            onClick={() => onDelete(a.id)}
            aria-label="Remove application"
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
            Worth <span className="figure font-semibold text-foreground">{money(a.estimated_value, a.currency)}/yr</span>
          </span>
        )}
        {a.deadline && (
          <span className={overdue ? "font-medium text-danger" : soon ? "font-medium text-accent" : "text-muted"}>
            Deadline {a.deadline}
            {a.days_until_deadline != null
              ? overdue
                ? " · overdue"
                : ` · ${a.days_until_deadline}d left`
              : ""}
          </span>
        )}
        {a.application_url && (
          <a href={a.application_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
            Apply ↗
          </a>
        )}
      </div>

      {a.documents.length > 0 && (
        <div className="mt-3 border-t border-border pt-3">
          <div className="mb-2 flex items-center justify-between text-[11px] font-medium uppercase tracking-wide text-muted">
            <span>Documents</span>
            <span>{done}/{a.documents.length} ready</span>
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
