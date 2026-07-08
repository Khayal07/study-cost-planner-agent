"use client";

import { useState } from "react";
import { generateMotivationLetter, type ApplicationOut } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/** AI motivation-letter drafting for a tracked application. The generated draft
 * is persisted server-side (application_id is sent), so the parent just needs
 * onSaved to refresh its local copy. */
export function LetterModal({
  a,
  onSaved,
  onClose,
}: {
  a: ApplicationOut;
  onSaved: (appId: number, letter: string) => void;
  onClose: () => void;
}) {
  const { t, locale } = useI18n();
  const [language, setLanguage] = useState<"en" | "az">(locale);
  const [tone, setTone] = useState<"formal" | "personal">("formal");
  const [notes, setNotes] = useState("");
  const [letter, setLetter] = useState(a.motivation_letter ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      const resp = await generateMotivationLetter({
        application_id: a.id,
        scholarship_name: a.scholarship_name,
        provider: a.provider,
        university_name: a.university_name,
        language,
        tone,
        user_notes: notes || null,
      });
      setLetter(resp.letter);
      onSaved(a.id, resp.letter);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("letter.error"));
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(letter);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked — text stays selectable */
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t("letter.title")}
      onClick={onClose}
    >
      <div
        className="card flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border bg-surface-2/60 px-5 py-3.5">
          <div>
            <h3 className="font-display text-sm font-semibold">{t("letter.title")}</h3>
            <p className="mt-0.5 text-xs text-muted">{a.scholarship_name}</p>
          </div>
          <button onClick={onClose} className="btn-ghost px-2.5 py-1.5 text-xs" aria-label={t("share.close")}>
            ✕
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <div className="flex flex-wrap gap-3">
            <div role="radiogroup" aria-label={t("letter.language")} className="inline-flex gap-1 rounded-xl border border-border bg-surface-2 p-1">
              {(["en", "az"] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  role="radio"
                  aria-checked={language === l}
                  onClick={() => setLanguage(l)}
                  className={`rounded-lg px-3 py-1 text-xs font-semibold uppercase transition-all ${
                    language === l ? "bg-surface text-foreground shadow-sm" : "text-muted hover:text-foreground"
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
            <div role="radiogroup" aria-label={t("letter.tone")} className="inline-flex gap-1 rounded-xl border border-border bg-surface-2 p-1">
              {(["formal", "personal"] as const).map((tn) => (
                <button
                  key={tn}
                  type="button"
                  role="radio"
                  aria-checked={tone === tn}
                  onClick={() => setTone(tn)}
                  className={`rounded-lg px-3 py-1 text-xs font-medium transition-all ${
                    tone === tn ? "bg-surface text-foreground shadow-sm" : "text-muted hover:text-foreground"
                  }`}
                >
                  {t(`letter.tone.${tn}`)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="letter-notes" className="field-label">{t("letter.notes")}</label>
            <textarea
              id="letter-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={600}
              rows={2}
              placeholder={t("letter.notesPh")}
              className="input min-h-[60px] w-full resize-y"
            />
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          {letter && (
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-[11px] font-medium uppercase tracking-wide text-muted">
                  {t("letter.draft")}
                </span>
                <button onClick={copy} className="btn-ghost px-2.5 py-1 text-xs">
                  {copied ? t("saved.copied") : t("letter.copy")}
                </button>
              </div>
              <div className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl border border-border bg-surface-2/50 p-4 text-sm leading-relaxed">
                {letter}
              </div>
              <p className="mt-2 text-[11px] text-muted">{t("letter.disclaimer")}</p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border bg-surface-2/40 px-5 py-3.5">
          <button onClick={generate} disabled={busy} className="btn-primary px-4 py-2 text-sm">
            {busy ? t("letter.generating") : letter ? t("letter.regenerate") : t("letter.generate")}
          </button>
        </div>
      </div>
    </div>
  );
}
