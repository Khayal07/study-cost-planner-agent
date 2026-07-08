"use client";

import { useEffect, useRef, useState } from "react";
import {
  postInterview,
  type InterviewFeedback,
  type InterviewTurn,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const MAX_HISTORY = 16; // mirror of the backend schema bound

function InterviewerMark() {
  return (
    <span className="chat-avatar mt-0.5">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="8" r="4" /><path d="M4 21v-1a7 7 0 0 1 14 0v1" />
      </svg>
    </span>
  );
}

/** AI interview practice: the model plays a scholarship/admissions interviewer,
 * then returns structured feedback. Session-local (not persisted). */
export function InterviewPanel() {
  const { t, locale } = useI18n();
  const [turns, setTurns] = useState<InterviewTurn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [feedback, setFeedback] = useState<InterviewFeedback | null>(null);
  const [started, setStarted] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, loading, feedback]);

  async function call(history: InterviewTurn[], action: "start" | "reply" | "finish") {
    setLoading(true);
    try {
      const res = await postInterview({ history: history.slice(-MAX_HISTORY), action, language: locale });
      if (res.done) {
        setDone(true);
        setFeedback(res.feedback);
        if (!res.feedback) setTurns((prev) => [...prev, { role: "interviewer", content: res.message }]);
      } else {
        setTurns([...history, { role: "interviewer", content: res.message }]);
      }
    } catch {
      setTurns((prev) => [...prev, { role: "interviewer", content: t("interview.error") }]);
      setDone(true);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function start() {
    setStarted(true);
    setTurns([]);
    setDone(false);
    setFeedback(null);
    void call([], "start");
  }

  function answer(text: string) {
    if (!text.trim() || loading || done) return;
    const history = [...turns, { role: "student" as const, content: text.trim().slice(0, 1200) }];
    setTurns(history);
    setInput("");
    void call(history, "reply");
  }

  function finish() {
    if (loading || done) return;
    void call(turns, "finish");
  }

  function restart() {
    setStarted(false);
    setTurns([]);
    setDone(false);
    setFeedback(null);
  }

  return (
    <>
      <div ref={scrollRef} className="chat-canvas flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
        {!started && (
          <div className="flex h-full flex-col items-center justify-center text-center animate-fade-in">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-primary-weak text-primary">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="8" r="4" /><path d="M4 21v-1a7 7 0 0 1 14 0v1" />
              </svg>
            </span>
            <h3 className="mt-3 font-display text-base font-semibold">{t("interview.title")}</h3>
            <p className="mt-1.5 max-w-sm text-sm text-muted">{t("interview.intro")}</p>
            <button onClick={start} className="btn-primary mt-4">{t("interview.start")}</button>
          </div>
        )}

        {turns.map((turn, i) =>
          turn.role === "student" ? (
            <div key={i} className="flex animate-fade-up justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-primary-fg shadow-sm">
                <span className="whitespace-pre-wrap text-sm leading-relaxed">{turn.content}</span>
              </div>
            </div>
          ) : (
            <div key={i} className="flex animate-fade-up justify-start gap-2.5">
              <InterviewerMark />
              <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-border bg-surface-2/70 px-4 py-2.5 text-foreground shadow-xs">
                <span className="whitespace-pre-wrap text-sm leading-relaxed">{turn.content}</span>
              </div>
            </div>
          ),
        )}

        {loading && (
          <div className="flex animate-fade-up justify-start gap-2.5">
            <InterviewerMark />
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

        {feedback && (
          <div className="card animate-fade-up border-primary/25 bg-primary-weak/30 p-4">
            <h4 className="mb-2 text-sm font-semibold text-primary">{t("interview.feedback")}</h4>
            {feedback.overall && <p className="mb-3 text-sm leading-relaxed">{feedback.overall}</p>}
            <div className="grid gap-3 sm:grid-cols-2">
              {feedback.strengths.length > 0 && (
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-primary">
                    {t("interview.strengths")}
                  </p>
                  <ul className="space-y-1 text-sm">
                    {feedback.strengths.map((s, i) => (
                      <li key={i} className="flex gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {feedback.improvements.length > 0 && (
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-accent">
                    {t("interview.improvements")}
                  </p>
                  <ul className="space-y-1 text-sm">
                    {feedback.improvements.map((s, i) => (
                      <li key={i} className="flex gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />{s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <button onClick={restart} className="btn-ghost mt-3 px-3 py-1.5 text-xs">
              {t("interview.again")}
            </button>
          </div>
        )}
      </div>

      <div className="border-t border-border bg-surface-2/40 p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            answer(input);
          }}
          className="flex items-center gap-2 rounded-2xl border border-border bg-surface px-2 py-1.5 shadow-xs transition-all focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20"
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={done ? t("interview.done") : t("interview.placeholder")}
            disabled={!started || done}
            maxLength={1200}
            className="flex-1 bg-transparent px-2 py-1.5 text-sm text-foreground outline-none placeholder:text-muted/70 disabled:opacity-60"
            aria-label={t("interview.placeholder")}
          />
          <button
            type="submit"
            disabled={loading || done || !started || !input.trim()}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary text-primary-fg shadow-sm transition-all hover:shadow-glow hover:brightness-[1.05] active:scale-95 disabled:pointer-events-none disabled:opacity-45"
            aria-label={t("chat.send")}
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M22 2 11 13M22 2l-7 20-4-9-9-4Z" />
            </svg>
          </button>
        </form>
        {started && !done && turns.length > 1 && (
          <button onClick={finish} disabled={loading} className="btn-ghost mt-2 px-3 py-1.5 text-xs">
            {t("interview.finish")}
          </button>
        )}
      </div>
    </>
  );
}
