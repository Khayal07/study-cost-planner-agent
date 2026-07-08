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
import { ScholarshipPanel } from "./ScholarshipPanel";
import { InterviewPanel } from "./InterviewPanel";
import { useI18n } from "@/lib/i18n";

type Turn = { role: "user" | "assistant"; text: string; res?: ChatResponse };
type Conversation = {
  id: string;
  title: string;
  turns: Turn[];
  profile: ChatProfile | null;
  updatedAt: number;
};

const STORE_KEY = "scp-chats-v1";

/** Starter prompts, grouped by the chat mode each one exercises (Discover /
 *  Afford / Compare / Ask) so the empty state teaches what the advisor can do. */
type Starter = { cat: "discover" | "afford" | "compare" | "ask"; prompt: string };
const STARTERS: Record<string, Starter[]> = {
  en: [
    { cat: "discover", prompt: "I want to study Computer Science in Germany, my budget is €12,000/year" },
    { cat: "afford", prompt: "Can I study at METU with €9,000?" },
    { cat: "compare", prompt: "Compare universities in Poland" },
    { cat: "ask", prompt: "Almaniyada viza nə qədərdir?" },
  ],
  az: [
    { cat: "discover", prompt: "Almaniyada Kompüter Elmləri oxumaq istəyirəm, büdcəm €12,000/il" },
    { cat: "afford", prompt: "€9,000 ilə METU-da oxuya bilərəmmi?" },
    { cat: "compare", prompt: "Polşadakı universitetləri müqayisə et" },
    { cat: "ask", prompt: "Almaniyada viza nə qədərdir?" },
  ],
};
const CAT_LABEL: Record<Starter["cat"], { en: string; az: string }> = {
  discover: { en: "Discover", az: "Kəşf et" },
  afford: { en: "Afford", az: "Büdcə" },
  compare: { en: "Compare", az: "Müqayisə" },
  ask: { en: "Ask", az: "Sual" },
};
function CatIcon({ cat }: { cat: Starter["cat"] }) {
  const p = { width: 15, height: 15, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
  if (cat === "discover")
    return <svg {...p}><circle cx="12" cy="12" r="9" /><path d="m15 9-2 4-4 2 2-4 4-2Z" /></svg>;
  if (cat === "afford")
    return <svg {...p}><path d="M3 8.5 12 4l9 4.5M4 10v7m16-7v7M3 20h18" /><path d="M9 13h6" /></svg>;
  if (cat === "compare")
    return <svg {...p}><path d="M4 20V9M10 20V4M16 20v-8M22 20H2" /></svg>;
  return <svg {...p}><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.4 2.3c-.7.3-.9.7-.9 1.4M12 17h.01" /></svg>;
}
/** The advisor's small "verified ledger" check, shown beside each of its replies. */
function AdvisorMark() {
  return (
    <span className="chat-avatar mt-0.5">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="m5 12 4.5 4.5L19 7" />
      </svg>
    </span>
  );
}

const SYMBOL: Record<string, string> = {
  EUR: "€", USD: "$", GBP: "£", TRY: "₺", PLN: "zł", HUF: "Ft", AZN: "₼",
};
const money = (amount: number, currency: string) =>
  `${SYMBOL[currency] ?? currency + " "}${Math.round(amount).toLocaleString()}`;

const newId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);
const emptyConversation = (): Conversation => ({
  id: newId(), title: "New chat", turns: [], profile: null, updatedAt: Date.now(),
});
/** Guard against corrupted/legacy localStorage: keep only well-formed conversations. */
function isValidConversation(c: unknown): c is Conversation {
  if (!c || typeof c !== "object") return false;
  const v = c as Record<string, unknown>;
  return (
    typeof v.id === "string" &&
    typeof v.title === "string" &&
    Array.isArray(v.turns) &&
    v.turns.every(
      (t) =>
        t &&
        typeof t === "object" &&
        (t as Turn).role !== undefined &&
        typeof (t as Turn).text === "string",
    )
  );
}

const titleFrom = (turns: Turn[]): string => {
  const first = turns.find((t) => t.role === "user");
  if (!first) return "New chat";
  return first.text.length > 38 ? first.text.slice(0, 38) + "…" : first.text;
};

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
  const { t } = useI18n();
  if (affordable === true)
    return <span className="chip border-primary/30 bg-primary-weak text-primary">{t("chat.fits")}</span>;
  if (affordable === false)
    return (
      <span className="chip border-warning/30 bg-accent-weak text-accent">
        {t("chat.over")}{gap != null ? ` ${money(Math.abs(gap), currency)}` : ""}
      </span>
    );
  return null;
}

/** A budget-fit meter rendered in the ledger spirit — teal when it fits. */
function MatchMeter({ score, affordable }: { score: number | null; affordable: boolean | null }) {
  const { t } = useI18n();
  if (score == null) return null;
  const tone = affordable ? "bg-primary" : score >= 50 ? "bg-warning" : "bg-danger";
  return (
    <div className="flex items-center gap-2" title={`${t("chat.matchTitle")}: ${score}/100`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-2">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${score}%` }} />
      </div>
      <span className="figure text-[11px] text-muted">{score}</span>
    </div>
  );
}

function CandidateCard({ c, score, valueMode = false, onExplore }: {
  c: CandidatePlan; score: number | null; valueMode?: boolean; onExplore: () => void;
}) {
  const { t } = useI18n();
  const cur = c.report_currency;
  const hasAid = c.total_scholarship_value > 0;
  const rankNum = valueMode ? c.value_rank ?? c.rank : c.rank;
  return (
    <div className="group rounded-xl border border-border bg-surface p-3.5 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <span className="figure mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-surface-2 text-[11px] font-semibold text-muted">
            {rankNum}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{c.university_name}</p>
            <p className="truncate text-xs text-muted">{c.city_name}, {c.country_name}</p>
          </div>
        </div>
        <div className="shrink-0 text-right">
          {valueMode && hasAid && c.net_total_annual != null ? (
            <>
              <p className="figure text-sm font-semibold text-primary">{money(c.net_total_annual, cur)}</p>
              <p className="text-[11px] text-muted line-through">{money(c.total_annual, cur)}/yr</p>
            </>
          ) : (
            <>
              <p className="figure text-sm font-semibold text-foreground">{money(c.total_annual, cur)}</p>
              <p className="text-[11px] text-muted">{t("chat.perYear")}</p>
            </>
          )}
        </div>
      </div>

      {hasAid && (
        <div className="mt-2">
          <span className="chip border-accent/30 bg-accent-weak text-accent">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M22 10 12 5 2 10l10 5 10-5Z" /><path d="M6 12v5c0 1 2.5 2.5 6 2.5s6-1.5 6-2.5v-5" />
            </svg>
            {t("chat.aid")}{money(c.total_scholarship_value, cur)}/yr
          </span>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <AffordBadge affordable={c.affordable} gap={c.budget_gap} currency={cur} />
          <MatchMeter score={score} affordable={c.affordable} />
        </div>
        <button
          onClick={onExplore}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary-weak"
        >
          {t("chat.explore")}
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </div>

      <div className="mt-2.5 flex gap-4 border-t border-border pt-2.5 text-[11px] text-muted">
        <span>{t("chat.tuition")} <span className="figure text-foreground">{c.annual_tuition > 0 ? money(c.annual_tuition, cur) : t("chat.free")}</span></span>
        <span>{t("chat.living")} <span className="figure text-foreground">{money(c.monthly_living, cur)}</span>{t("chat.perMo")}</span>
      </div>
    </div>
  );
}

/** Grounded figures with a clickable source on each — the chat's ledger. */
function SourceLedger({ c }: { c: CandidatePlan }) {
  const { t } = useI18n();
  return (
    <div className="mt-2 flex flex-col gap-1.5 rounded-xl border border-border bg-surface p-2.5">
      <p className="mb-0.5 text-[11px] font-medium uppercase tracking-wide text-muted">
        {t("chat.breakdown")}
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
  const { t, locale } = useI18n();
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [panelMode, setPanelMode] = useState<"advisor" | "interview">("advisor");
  const loadedRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Load persisted conversations once (client only).
  useEffect(() => {
    let initial: Conversation[] = [];
    try {
      const raw = localStorage.getItem(STORE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      // Drop anything that doesn't match the current shape (corruption / old versions).
      initial = Array.isArray(parsed) ? parsed.filter(isValidConversation) : [];
    } catch {
      initial = [];
    }
    if (initial.length === 0) initial = [emptyConversation()];
    setConvos(initial);
    setActiveId(initial[0].id);
    loadedRef.current = true;
  }, []);

  // Persist on change (after the initial load).
  useEffect(() => {
    if (!loadedRef.current) return;
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(convos));
    } catch {
      /* quota / private mode — non-fatal */
    }
  }, [convos]);

  const active = convos.find((c) => c.id === activeId) ?? null;
  const turns = active?.turns ?? [];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, loading]);

  function patchActive(fn: (c: Conversation) => Conversation) {
    setConvos((prev) => prev.map((c) => (c.id === activeId ? fn(c) : c)));
  }

  async function send(message: string) {
    if (!message.trim() || loading || !active) return;
    const sentProfile = active.profile;
    const userTurn: Turn = { role: "user", text: message };
    patchActive((c) => ({
      ...c,
      turns: [...c.turns, userTurn],
      title: c.turns.length === 0 ? titleFrom([userTurn]) : c.title,
      updatedAt: Date.now(),
    }));
    setInput("");
    setLoading(true);
    try {
      const res = await postChat(message, reportCurrency, sentProfile);
      patchActive((c) => ({
        ...c,
        turns: [...c.turns, { role: "assistant", text: res.answer, res }],
        profile: res.profile,
        updatedAt: Date.now(),
      }));
    } catch {
      patchActive((c) => ({
        ...c,
        turns: [...c.turns, { role: "assistant", text: t("chat.errReach") }],
        updatedAt: Date.now(),
      }));
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function newChat() {
    if (active && active.turns.length === 0) {
      inputRef.current?.focus();
      return;
    }
    const c = emptyConversation();
    setConvos((prev) => [c, ...prev]);
    setActiveId(c.id);
    setInput("");
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function selectConvo(id: string) {
    setActiveId(id);
    setInput("");
  }

  function deleteConvo(id: string) {
    const next = convos.filter((c) => c.id !== id);
    if (next.length === 0) {
      const c = emptyConversation();
      setConvos([c]);
      setActiveId(c.id);
      return;
    }
    setConvos(next);
    if (id === activeId) setActiveId(next[0].id);
  }

  async function downloadReport(p: ChatProfile) {
    if (exporting) return;
    setExporting(true);
    try {
      await exportPdf(profileToPlanRequest(p));
    } catch {
      patchActive((c) => ({
        ...c,
        turns: [...c.turns, { role: "assistant", text: t("chat.errPdf") }],
        updatedAt: Date.now(),
      }));
    } finally {
      setExporting(false);
    }
  }

  const listConvos = [...convos].sort((a, b) => b.updatedAt - a.updatedAt);

  function renderAssistant(res: ChatResponse) {
    const valueMode = res.mode === "value";
    // Card list for discovery/compare/value, and for a multi-option scholarships answer.
    const showCards =
      res.mode === "discovery" ||
      res.mode === "compare" ||
      res.mode === "value" ||
      (res.mode === "scholarships" && !res.detail && res.candidates.length > 0);
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
                valueMode={valueMode}
                onExplore={() =>
                  send(
                    valueMode || res.mode === "scholarships"
                      ? `Scholarships at ${c.university_name}`
                      : `Tell me about ${c.university_name}`,
                  )
                }
              />
            ))}
          </div>
        )}

        {(res.mode === "detail" || res.mode === "affordability") && res.detail && (
          <SourceLedger c={res.detail} />
        )}

        {/* Scholarships for a single focused university */}
        {res.detail && res.detail.scholarships && res.detail.scholarships.length > 0 &&
          (res.mode === "scholarships" || res.mode === "detail" || res.mode === "affordability") && (
            <div className="mt-3">
              <ScholarshipPanel
                candidate={res.detail}
                onExportLive={
                  res.can_export && res.profile
                    ? (sel, cand) =>
                        exportPdf({
                          ...profileToPlanRequest(res.profile),
                          focus_program_id: cand.program_id,
                          extra_scholarships: sel,
                        })
                    : undefined
                }
              />
            </div>
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
                {exporting ? t("chat.preparing") : t("chat.download")}
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
    <div className="grid gap-4 lg:grid-cols-[15rem_1fr]">
      {/* Conversation rail */}
      <aside className="lg:sticky lg:top-24 lg:self-start">
        <button
          onClick={newChat}
          className="mb-3 flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm font-medium transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
          {t("chat.newChat")}
        </button>

        <div className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
          {listConvos.map((c) => {
            const isActive = c.id === activeId;
            const label = c.title === "New chat" ? t("chat.newChat") : c.title;
            return (
              <div key={c.id} className="group relative shrink-0 lg:shrink">
                <button
                  onClick={() => selectConvo(c.id)}
                  className={`w-44 truncate rounded-xl border px-3 py-2 pr-7 text-left text-sm transition-colors lg:w-full ${
                    isActive
                      ? "border-primary/50 bg-primary-weak/50 text-foreground"
                      : "border-border bg-surface-2/40 text-muted hover:border-primary/30 hover:text-foreground"
                  }`}
                  title={label}
                >
                  {label}
                </button>
                <button
                  onClick={() => deleteConvo(c.id)}
                  aria-label={t("chat.delete")}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted opacity-0 transition-opacity hover:bg-danger/10 hover:text-danger focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>
            );
          })}
        </div>
      </aside>

      {/* Chat card */}
      <div className="card flex h-[calc(100dvh-11rem)] max-h-[820px] min-h-[460px] flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-border bg-surface-2/60 px-5 py-3.5">
          <span className="relative grid h-9 w-9 place-items-center rounded-xl bg-primary-weak text-primary">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
            </svg>
            <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-surface-2 bg-success" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h2 className="font-display text-sm font-semibold leading-none">{t("chat.advisor")}</h2>
            <p className="mt-1 truncate text-xs text-muted">{t("chat.advisorSub")}</p>
          </div>
          <div
            role="radiogroup"
            aria-label={t("interview.mode")}
            className="ml-auto inline-flex shrink-0 gap-1 rounded-xl border border-border bg-surface p-1"
          >
            {(["advisor", "interview"] as const).map((m) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={panelMode === m}
                onClick={() => setPanelMode(m)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
                  panelMode === m ? "bg-primary text-primary-fg shadow-sm" : "text-muted hover:text-foreground"
                }`}
              >
                {t(`interview.mode.${m}`)}
              </button>
            ))}
          </div>
          <span
            className="chip shrink-0 border-primary/20 bg-primary-weak text-primary"
            title={locale === "az" ? "Cavablar bu valyutada" : "Answers shown in this currency"}
          >
            {SYMBOL[reportCurrency] ?? reportCurrency} {reportCurrency}
          </span>
        </div>

        {panelMode === "interview" ? (
          <InterviewPanel />
        ) : (
        <>
        {/* Messages */}
        <div ref={scrollRef} className="chat-canvas flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
          {turns.length === 0 && (
            <div className="animate-fade-in">
              <p className="mb-4 text-sm text-muted">
                {t("chat.intro")}
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {STARTERS[locale].map(({ cat, prompt }) => (
                  <button
                    key={prompt}
                    onClick={() => send(prompt)}
                    className="group flex items-start gap-3 rounded-xl border border-border bg-surface-2/50 p-3 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm"
                  >
                    <span className="chat-avatar mt-0.5 transition-colors group-hover:ring-primary/40">
                      <CatIcon cat={cat} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[10px] font-semibold uppercase tracking-wider text-primary/80">
                        {CAT_LABEL[cat][locale as "en" | "az"]}
                      </span>
                      <span className="mt-0.5 block text-[13px] leading-snug text-foreground">{prompt}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn, i) =>
            turn.role === "user" ? (
              <div key={i} className="flex animate-fade-up justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-primary-fg shadow-sm">
                  <span className="whitespace-pre-wrap text-sm leading-relaxed">{turn.text}</span>
                </div>
              </div>
            ) : (
              <div key={i} className="flex animate-fade-up justify-start gap-2.5">
                <AdvisorMark />
                <div className="min-w-0 flex-1">
                  <div className="rounded-2xl rounded-bl-md border border-border bg-surface-2/70 px-4 py-2.5 text-foreground shadow-xs">
                    <RichText text={turn.text} />
                  </div>
                  {turn.res && renderAssistant(turn.res)}
                </div>
              </div>
            ),
          )}

          {loading && (
            <div className="flex animate-fade-up justify-start gap-2.5">
              <AdvisorMark />
              <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-border bg-surface-2/70 px-4 py-3 shadow-xs">
                {[0, 1, 2].map((d) => (
                  <span
                    key={d}
                    className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary/60"
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
            className="flex items-center gap-2 rounded-2xl border border-border bg-surface px-2 py-1.5 shadow-xs transition-all focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20"
          >
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("chat.placeholder")}
              className="flex-1 bg-transparent px-2 py-1.5 text-sm text-foreground outline-none placeholder:text-muted/70"
              aria-label={t("chat.message")}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary text-primary-fg shadow-sm transition-all hover:shadow-glow hover:brightness-[1.05] active:scale-95 disabled:pointer-events-none disabled:opacity-45"
              aria-label={t("chat.send")}
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M22 2 11 13M22 2l-7 20-4-9-9-4Z" />
              </svg>
            </button>
          </form>
          <p className="mt-2 flex items-center gap-1.5 px-1 text-[11px] text-muted">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="text-primary/70">
              <path d="m9 12 2 2 4-4" /><circle cx="12" cy="12" r="9" />
            </svg>
            {locale === "az"
              ? "Hər rəqəm istinad edilmiş mənbəyə əsaslanır"
              : "Every figure is grounded in a cited source"}
          </p>
        </div>
        </>
        )}
      </div>
    </div>
  );
}
