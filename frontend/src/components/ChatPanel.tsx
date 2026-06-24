"use client";

import { useState } from "react";
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

  async function send(message: string) {
    if (!message.trim() || loading) return;
    setTurns((t) => [...t, { role: "user", text: message }]);
    setInput("");
    setLoading(true);
    try {
      const res = await postChat(message, reportCurrency);
      setTurns((t) => [...t, { role: "assistant", text: res.answer, res }]);
    } catch (e) {
      setTurns((t) => [...t, { role: "assistant", text: `Error: ${String(e)}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-[600px] flex-col rounded-xl border border-slate-200 bg-white">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {turns.length === 0 && (
          <div className="text-sm text-muted">
            <p className="mb-2">Ask in natural language. Try:</p>
            <div className="flex flex-col gap-1.5">
              {SAMPLES.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-left text-xs hover:border-brand"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) => (
          <div key={i} className={t.role === "user" ? "text-right" : ""}>
            <div
              className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm ${
                t.role === "user" ? "bg-brand text-white" : "bg-slate-100 text-ink"
              }`}
            >
              {t.text}
            </div>

            {t.res?.figures && t.res.figures.length > 0 && (
              <div className="mt-2 space-y-1">
                {t.res.figures.map((f, j) => (
                  <div key={j} className="flex items-center gap-2 text-xs">
                    <span className="text-muted">{f.label}:</span>
                    <span className="font-semibold">
                      {f.amount.toLocaleString(undefined, { maximumFractionDigits: 0 })} {f.currency}
                    </span>
                    <CitationChip citation={f.citation} confidence={f.confidence} />
                  </div>
                ))}
              </div>
            )}

            {t.res?.mode === "plan" && t.res.plan && (
              <div className="mt-2 inline-block rounded-lg bg-blue-50 px-3 py-1.5 text-xs text-brand">
                Full plan built: {t.res.plan.candidates.length} options · verification{" "}
                {t.res.plan.verification?.overall}. Switch to the Form tab to view charts & PDF.
              </div>
            )}
          </div>
        ))}

        {loading && <div className="text-sm text-muted">Thinking…</div>}
      </div>

      <div className="border-t border-slate-200 p-3">
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
            className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
