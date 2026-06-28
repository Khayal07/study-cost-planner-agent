"use client";

import { useEffect, useRef, useState } from "react";

/** Counts up to `to` once, when first scrolled into view; respects reduced motion. */
function useCountUp(to: number, durationMs = 1100) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement | null>(null);
  const done = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setValue(to);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !done.current) {
          done.current = true;
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
        {value}
        {suffix}
      </span>
      <span className="mt-0.5 text-xs text-muted">{label}</span>
    </div>
  );
}

export function Hero() {
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
          <Stat to={8} label="countries" />
          <Stat to={25} label="universities" />
          <Stat to={130} label="sourced figures" />
        </div>
      </div>
    </section>
  );
}
