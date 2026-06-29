"use client";

import { useEffect, useRef, useState } from "react";

import { getStats } from "@/lib/api";

/** Counts up to `to` once visible (re-animates if `to` arrives later); respects reduced motion. */
function useCountUp(to: number, durationMs = 1100) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || to <= 0) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setValue(to);
      return;
    }
    let started = false;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !started) {
          started = true;
          const start = performance.now();
          const tick = (now: number) => {
            const p = Math.min(1, (now - start) / durationMs);
            const eased = 1 - Math.pow(1 - p, 3);
            setValue(Math.round(eased * to));
            if (p < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [to, durationMs]);

  return { value, ref };
}

function Stat({ to, suffix, label }: { to: number; suffix?: string; label: string }) {
  const { value, ref } = useCountUp(to);
  return (
    <div className="flex flex-col">
      <span ref={ref} className="figure text-2xl font-semibold text-foreground sm:text-3xl">
        {to <= 0 ? "—" : value}
        {suffix}
      </span>
      <span className="mt-0.5 text-xs text-muted">{label}</span>
    </div>
  );
}

export function Hero() {
  // Live dataset counters — never hardcoded; stays in sync as the seed grows.
  const [stats, setStats] = useState({ countries: 0, universities: 0, cited_figures: 0 });
  useEffect(() => {
    getStats()
      .then((s) =>
        setStats({
          countries: s.countries,
          universities: s.universities,
          cited_figures: s.cited_figures,
        }),
      )
      .catch(() => {
        /* leave dashes if the catalog is unreachable */
      });
  }, []);

  return (
    <section className="relative overflow-hidden border-b border-border">
      <div className="pointer-events-none absolute inset-0 hero-grid" aria-hidden="true" />
      <div className="relative mx-auto max-w-6xl px-4 pb-12 pt-14 sm:px-6 sm:pb-16 sm:pt-20">
        <div className="animate-fade-up">
          <span className="chip border border-primary/30 bg-primary-weak text-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            AI study-cost intelligence
          </span>
          <h1 className="mt-5 max-w-3xl font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
            The <span className="text-primary">real cost</span> of studying abroad —
            not just tuition.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
            Tuition, living, insurance, visa, transport and the hidden fees nobody
            quotes you. Every figure is converted to your currency and traced to a
            cited source — <span className="font-medium text-foreground">sourced</span> or{" "}
            <span className="font-medium text-foreground">clearly flagged as an estimate</span>.
          </p>
        </div>

        <div className="mt-10 grid w-full max-w-xl grid-cols-3 gap-6 rounded-2xl border border-border bg-surface/60 p-5 shadow-sm animate-fade-up sm:gap-8">
          <Stat to={stats.countries} label="countries" />
          <Stat to={stats.universities} label="universities" />
          <Stat to={stats.cited_figures} label="cited figures" />
        </div>
      </div>
    </section>
  );
}
