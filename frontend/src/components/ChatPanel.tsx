"use client";

import { useEffect, useRef, useState } from "react";
import {
  postChat,
  exportPdf,
  profileToPlanRequest,
  type ChatResponse,
  type ChatProfile,
  type CandidatePlan,
} from "@/lib/api";
import { CitationChip } from "./CitationChip";

type Turn = { role: "user" | "assistant"; text: string; res?: ChatResponse };

const SAMPLES = [
  "I want to study Computer Science in Germany, my budget is €12,000/year",
  "Can I study at METU with €9,000?",
  "Compare universities in Poland",
  "Almaniyada viza nə qədərdir?",
];

const SYMBOL: Record<string, string> = {
  EUR: "€", USD: "$", GBP: "£", TRY: "₺", PLN: "zł", HUF: "Ft", AZN: "₼",
};
const money = (amount: number, currency: string) =>
  `${SYMBOL[currency] ?? currency + " "}${Math.round(amount).toLocaleString()}`;

/** Render the advisor's lightweight markdown (**bold** + line breaks). */
function RichText({ text }: { text: string }) {
  return (
    <div className="whitespace-pre-wrap text-sm leading-relaxed">
      {text.split("\n").map((line, i) => (
        <p key={i} className={line.trim() === "" ? "h-2" : undefined}>
          {line.split(/(\*\*[^*]+\*\*)/g).map((seg, j) =>
            seg.startsWith("**") && seg.endsWith("**") ? (
              <strong key={j} className="font-semibold text-foreground">{seg.slice(2, -2)}</strong>
            ) : (
              <span key={j}>{seg}</span>
            ),
          )}
        </p>
      ))}
    </div>
  );
}

function AffordBadge({ affordable, gap, currency }: {
  affordable: boolean | null; gap?: number | null; currency: string;
}) {
  if (affordable === true)
    return <span className="chip border-primary/30 bg-primary-weak text-primary">Fits budget</span>;
  if (affordable === false)
    return (
      <span className="chip border-warning/30 bg-accent-weak text-accent">
        Over{gap != null ? ` by ${money(Math.abs(gap), currency)}` : ""}
      </span>
    );
  return null;
}

/** A budget-fit meter rendered in the ledger spirit — teal when it fits. */
function MatchMeter({ score, affordable }: { score: number | null; affordable: boolean | null }) {
  if (score == null) return null;
  const tone = affordable ? "bg-primary" : score >= 50 ? "bg-warning" : "bg-danger";
  return (
    <div className="flex items-center gap-2" title={`Budget-fit match score: ${score}/100`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-2">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${score}%` }} />
      </div>
      <span className="figure text-[11px] text-muted">{score}</span>
    </div>
  );
}

function CandidateCard({ c, score, onExplore }: {
  c: CandidatePlan; score: number | null; onExplore: () => void;
}) {
  const cur = c.report_currency;
  return (
    <div className="group rounded-xl border border-border bg-surface p-3.5 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <span className="figure mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-surface-2 text-[11px] font-semibold text-muted">
            {c.rank}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{c.university_name}</p>
            <p className="truncate text-xs text-muted">{c.city_name}, {c.country_name}</p>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="figure text-sm font-semibold text-foreground">{money(c.total_annual, cur)}</p>
          <p className="text-[11px] text-muted">/year</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <AffordBadge affordable={c.affordable} gap={c.budget_gap} currency={cur} />
          <MatchMeter score={score} affordable={c.affordable} />
        </div>
        <button
          onClick={onExplore}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary-weak"
        >
          Explore
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </div>

      <div className="mt-2.5 flex gap-4 border-t border-border pt-2.5 text-[11px] text-muted">
        <span>Tuition <span className="figure text-foreground">{c.annual_tuition > 0 ? money(c.annual_tuition, cur) : "free"}</span></span>
        <span>Living <span className="figure text-foreground">{money(c.monthly_living, cur)}</span>/mo</span>
      </div>
    </div>
  );
}

/** Grounded figures with a clickable source on each — the chat's ledger. */
function SourceLedger({ c }: { c: CandidatePlan }) {
  return (
    <div className="mt-2 flex flex-col gap-1.5 rounded-xl border border-border bg-surface p-2.5">
      <p className="mb-0.5 text-[11px] font-medium uppercase tracking-wide text-muted">
        Annual breakdown · every figure cited
      </p>
      {c.lines.map((line, i) => (
        <div key={i} className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <span className="text-muted">{line.label}</span>
          <span className="flex items-center gap-2">
            <span className="figure font-semibold text-foreground">{money(line.amount, line.currency)}</span>
            <CitationChip citation={line.citation} confidence={line.confidence} />
          </span>
        </div>
      ))}
    </div>
  );
}

export function ChatPanel({ reportCurrency }: { reportCurrency: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [profile, setProfile] = useState<ChatProfile | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
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
      const res = await postChat(message, reportCurrency, profile);
      setProfile(res.profile);
      setTurns((t) => [...t, { role: "assistant", text: res.answer, res }]);
    } catch {
      setTurns((t) => [
        ...t,
        { role: "assistant", text: "I couldn't reach the planning service. Please check the backend is running and try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function downloadReport(p: ChatProfile) {
    if (exporting) return;
    setExporting(true);
    try {
      await exportPdf(profileToPlanRequest(p));
    } catch {
      setTurns((t) => [
        ...t,
        { role: "assistant", text: "I couldn't generate the PDF just now. Please try again in a moment." },
      ]);
    } finally {
      setExporting(false);
    }
  }

  function renderAssistant(res: ChatResponse) {
    const showCards = res.mode === "discovery" || res.mode === "compare";
    const scoreById = new Map(res.profile.last_candidates.map((r) => [r.program_id, r.match_score]));
    // Drop chips already covered by richer affordances: per-option "Explore" (cards)
    // and any "report" chip when the real Download button is shown.
    const chips = res.suggestions.filter(
      (s) =>
        !(showCards && s.label.startsWith("Explore")) &&
        !(res.can_export && /report/i.test(s.label)),
    );

    return (
      <>
        {showCards && res.candidates.length > 0 && (
          <div className="mt-3 flex flex-col gap-2">
            {res.candidates.map((c) => (
              <CandidateCard
                key={c.program_id}
                c={c}
                score={scoreById.get(c.program_id) ?? null}
                onExplore={() => send(`Tell me about ${c.university_name}`)}
              />
            ))}
          </div>
        )}

        {(res.mode === "detail" || res.mode === "affordability") && res.detail && (
          <SourceLedger c={res.detail} />
        )}

        {res.mode === "answer" && res.figures.length > 0 && (
          <div className="mt-2 flex flex-col gap-1.5 rounded-xl border border-border bg-surface p-2.5">
            {res.figures.map((f, j) => (
              <div key={j} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="text-muted">{f.label}</span>
                <span className="flex items-center gap-2">
                  <span className="figure font-semibold text-foreground">{money(f.amount, f.currency)}</span>
                  <CitationChip citation={f.citation} confidence={f.confidence} />
                </span>
              </div>
            ))}
          </div>
        )}

        {(chips.length > 0 || res.can_export) && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {res.can_export && (
              <button
                onClick={() => downloadReport(res.profile)}
                disabled={exporting}
                className="btn-primary px-3 py-1.5 text-xs"
              >
                {exporting ? "Preparing…" : "Download report"}
                {!exporting && (
                  <svg className="ml-1" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14" />
                  </svg>
                )}
              </button>
            )}
            {chips.map((s) => (
              <button
                key={s.label}
                onClick={() => send(s.message)}
                className="chip transition-colors hover:border-primary/40 hover:text-foreground"
              >
                {s.label}
              </button>
            ))}
          </div>
        )}
      </>
    );
  }

  return (
    <div className="card flex h-[640px] flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border bg-surface-2/60 px-5 py-3.5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary-weak text-primary">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
          </svg>
        </span>
        <div>
          <h2 className="font-display text-sm font-semibold leading-none">Study Abroad Advisor</h2>
          <p className="mt-1 text-xs text-muted">Remembers your plan · every figure is cited</p>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
        {turns.length === 0 && (
          <div className="animate-fade-in">
            <p className="mb-3 text-sm text-muted">
              Tell me your budget and where you&apos;d like to study — I&apos;ll find universities that
              fit and explain every cost. Try:
            </p>
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
            <div className={t.role === "user" ? "max-w-[85%]" : "w-full max-w-[92%]"}>
              <div
                className={`rounded-2xl px-4 py-2.5 ${
                  t.role === "user"
                    ? "rounded-br-md bg-primary text-primary-fg shadow-sm"
                    : "rounded-bl-md border border-border bg-surface-2/70 text-foreground"
                }`}
              >
                {t.role === "user" ? (
                  <span className="whitespace-pre-wrap text-sm leading-relaxed">{t.text}</span>
                ) : (
                  <RichText text={t.text} />
                )}
              </div>
              {t.role === "assistant" && t.res && renderAssistant(t.res)}
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
            placeholder="e.g. I want to study CS in Poland, budget €10,000"
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
