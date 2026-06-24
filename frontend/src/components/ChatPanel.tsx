"use client";

import { useEffect, useRef, useState } from "react";
import { postChat, type ChatResponse } from "@/lib/api";
import { CitationChip } from "./CitationChip";

type Turn = { role: "user" | "assistant"; text: string; res?: ChatResponse };

const SAMPLES = [
  "I want to study Computer Science in Germany, my budget is €8000/year",
  "Almaniyada viza nə qədərdir?",
  "Polşada təhsil haqqı nə qədərdir?",
];

export function ChatPanel({ reportCurrency }: { reportCurrency: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, loading]);

  async function send(message: string) {
    if (!message.trim() || loading) return;
    setTurns((t) => [...t, { role: "user", text: message }]);
    setInput("");
    setLoading(true);
    try {
      const res = await postChat(message, reportCurrency);
      setTurns((t) => [...t, { role: "assistant", text: res.answer, res }]);
    } catch {
      setTurns((t) => [
        ...t,
        { role: "assistant", text: "I couldn't reach the planning service. Please check the backend and try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card flex h-[620px] flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border bg-surface-2/60 px-5 py-3.5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary-weak text-primary">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
          </svg>
        </span>
        <div>
          <h2 className="font-display text-sm font-semibold leading-none">Ask anything</h2>
          <p className="mt-1 text-xs text-muted">Same grounded engine · answers cite sources</p>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
        {turns.length === 0 && (
          <div className="animate-fade-in">
            <p className="mb-3 text-sm text-muted">Try one of these to get started:</p>
            <div className="flex flex-col gap-2">
              {SAMPLES.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="group flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2/50 px-3.5 py-2.5 text-left text-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm"
                >
                  <span>{s}</span>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-muted transition-colors group-hover:text-primary" aria-hidden="true">
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) => (
          <div key={i} className={`flex animate-fade-up ${t.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={t.role === "user" ? "max-w-[85%]" : "max-w-[90%]"}>
              <div
                className={`whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  t.role === "user"
                    ? "rounded-br-md bg-primary text-primary-fg shadow-sm"
                    : "rounded-bl-md border border-border bg-surface-2/70 text-foreground"
                }`}
              >
                {t.text}
              </div>

              {t.res?.figures && t.res.figures.length > 0 && (
                <div className="mt-2 flex flex-col gap-1.5 rounded-xl border border-border bg-surface p-2.5">
                  {t.res.figures.map((f, j) => (
                    <div key={j} className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="text-muted">{f.label}</span>
                      <span className="figure font-semibold text-foreground">
                        {f.amount.toLocaleString(undefined, { maximumFractionDigits: 0 })} {f.currency}
                      </span>
                      <CitationChip citation={f.citation} confidence={f.confidence} />
                    </div>
                  ))}
                </div>
              )}

              {t.res?.mode === "plan" && t.res.plan && (
                <div className="mt-2 inline-flex items-center gap-2 rounded-xl border border-primary/25 bg-primary-weak/50 px-3 py-1.5 text-xs text-primary">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="m9 12 2 2 4-4" />
                    <circle cx="12" cy="12" r="9" />
                  </svg>
                  Full plan built: {t.res.plan.candidates.length} options · verification{" "}
                  {t.res.plan.verification?.overall}. Open the Budget form tab for charts & PDF.
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-border bg-surface-2/70 px-4 py-3">
              {[0, 1, 2].map((d) => (
                <span
                  key={d}
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted"
                  style={{ animationDelay: `${d * 0.15}s` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-border bg-surface-2/40 p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. I want to study CS in Poland, budget 10000 EUR"
            className="input"
            aria-label="Message"
          />
          <button type="submit" disabled={loading || !input.trim()} className="btn-primary px-3.5" aria-label="Send message">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M22 2 11 13M22 2l-7 20-4-9-9-4Z" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
