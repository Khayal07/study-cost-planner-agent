"use client";

import { useMemo, useState } from "react";
import type { ApplicationOut } from "@/lib/api";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const ymd = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Month grid of tracked scholarship deadlines. Pure frontend over Application.deadline. */
export function DeadlineCalendar({ apps }: { apps: ApplicationOut[] }) {
  const withDeadline = apps.filter((a) => a.deadline);
  const today = new Date();
  const todayKey = ymd(today);

  // Default to the month of the nearest upcoming (or earliest) deadline.
  const initial = useMemo(() => {
    const dates = withDeadline
      .map((a) => new Date(a.deadline as string))
      .filter((d) => !Number.isNaN(d.getTime()))
      .sort((a, b) => a.getTime() - b.getTime());
    const next = dates.find((d) => d >= today) ?? dates[0] ?? today;
    return { year: next.getFullYear(), month: next.getMonth() };
  }, [apps]); // eslint-disable-line react-hooks/exhaustive-deps

  const [view, setView] = useState(initial);

  // Group applications by their deadline day.
  const byDay = useMemo(() => {
    const m = new Map<string, ApplicationOut[]>();
    for (const a of withDeadline) {
      const key = (a.deadline as string).slice(0, 10);
      (m.get(key) ?? m.set(key, []).get(key)!).push(a);
    }
    return m;
  }, [apps]); // eslint-disable-line react-hooks/exhaustive-deps

  const first = new Date(view.year, view.month, 1);
  // Monday-first offset (JS getDay: Sun=0).
  const lead = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(view.year, view.month + 1, 0).getDate();
  const cells: (number | null)[] = [
    ...Array(lead).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  function shift(delta: number) {
    setView((v) => {
      const d = new Date(v.year, v.month + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });
  }

  return (
    <div className="card p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-display text-base font-semibold">
          {MONTHS[view.month]} {view.year}
        </h3>
        <div className="flex gap-1">
          <button onClick={() => shift(-1)} aria-label="Previous month" className="btn-ghost px-2 py-1.5">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
          </button>
          <button onClick={() => setView({ year: today.getFullYear(), month: today.getMonth() })} className="btn-ghost px-3 py-1.5 text-xs">
            Today
          </button>
          <button onClick={() => shift(1)} aria-label="Next month" className="btn-ghost px-2 py-1.5">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M9 18l6-6-6-6" /></svg>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center text-[11px] font-medium text-muted">
        {WEEKDAYS.map((w) => (
          <div key={w} className="pb-1">{w}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, i) => {
          if (day == null) return <div key={i} className="min-h-[64px] rounded-lg" />;
          const key = ymd(new Date(view.year, view.month, day));
          const hits = byDay.get(key) ?? [];
          const isToday = key === todayKey;
          const overdue = key < todayKey;
          return (
            <div
              key={i}
              className={`min-h-[64px] rounded-lg border p-1 text-left ${
                hits.length
                  ? overdue
                    ? "border-danger/30 bg-danger/5"
                    : "border-accent/40 bg-accent-weak/40"
                  : "border-border bg-surface-2/30"
              }`}
            >
              <div className={`mb-0.5 text-[11px] font-semibold ${isToday ? "text-primary" : "text-muted"}`}>
                {isToday ? (
                  <span className="inline-grid h-4 w-4 place-items-center rounded-full bg-primary text-[10px] text-primary-fg">{day}</span>
                ) : (
                  day
                )}
              </div>
              <div className="space-y-0.5">
                {hits.slice(0, 2).map((a) => (
                  <div
                    key={a.id}
                    title={`${a.scholarship_name}${a.university_name ? ` · ${a.university_name}` : ""}`}
                    className={`truncate rounded px-1 py-0.5 text-[10px] font-medium ${
                      overdue ? "bg-danger/15 text-danger" : "bg-accent/20 text-accent"
                    }`}
                  >
                    {a.scholarship_name}
                  </div>
                ))}
                {hits.length > 2 && (
                  <div className="px-1 text-[10px] text-muted">+{hits.length - 2} more</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {withDeadline.length === 0 && (
        <p className="mt-3 text-center text-xs text-muted">None of your tracked applications has a deadline yet.</p>
      )}
    </div>
  );
}
