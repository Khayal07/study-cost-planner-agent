"use client";

import { useRef, useState } from "react";
import { analyzeTranscript, updateProfile, type TranscriptExtraction } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPT = "image/png,image/jpeg,image/webp,application/pdf";

/** Upload a transcript → AI extracts GPA/degree → user confirms → GPA lands in
 * the wizard field (and the saved profile when signed in). Nothing is written
 * without the explicit Apply click. */
export function TranscriptUpload({ onApply }: { onApply: (gpa: number) => void }) {
  const { t } = useI18n();
  const { isAuthed, openAuth } = useAuth();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [result, setResult] = useState<TranscriptExtraction | null>(null);
  const [applied, setApplied] = useState(false);

  async function onFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    setResult(null);
    setNote(null);
    setApplied(false);
    if (file.size > MAX_BYTES) {
      setError(t("transcript.tooBig"));
      return;
    }
    setBusy(true);
    try {
      const resp = await analyzeTranscript(file);
      setResult(resp.extraction);
      setNote(resp.note);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("transcript.error"));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function apply() {
    if (!result?.gpa_on_4_scale) return;
    const gpa = Math.round(result.gpa_on_4_scale * 100) / 100;
    onApply(gpa);
    setApplied(true);
    try {
      // Persist to the account profile too (endpoint is auth-only anyway).
      await updateProfile({ nationality: null, gpa, language_test: null });
    } catch {
      /* wizard field is already filled — profile sync is best-effort */
    }
  }

  if (!isAuthed) {
    return (
      <p className="rounded-xl border border-dashed border-border bg-surface-2/40 px-3 py-2.5 text-[11px] leading-relaxed text-muted">
        {t("transcript.signin")}{" "}
        <button type="button" onClick={openAuth} className="font-medium text-primary hover:underline">
          {t("saved.signinBtn")}
        </button>
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-dashed border-border bg-surface-2/40 p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium">{t("transcript.title")}</p>
          <p className="text-[11px] text-muted">{t("transcript.hint")}</p>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          className="btn-ghost shrink-0 px-3 py-1.5 text-xs"
        >
          {busy ? t("transcript.analyzing") : t("transcript.upload")}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => onFile(e.target.files?.[0])}
          aria-label={t("transcript.title")}
        />
      </div>

      {error && <p className="mt-2 text-[11px] text-danger">{error}</p>}
      {note && !error && <p className="mt-2 text-[11px] text-muted">{note}</p>}

      {result && result.gpa_on_4_scale != null && (
        <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-primary/30 bg-primary-weak/30 px-3 py-2">
          <div className="text-xs">
            <span className="figure font-semibold text-primary">
              GPA {result.gpa_on_4_scale.toFixed(2)} / 4.0
            </span>
            {result.gpa != null && result.gpa_scale != null && result.gpa_scale !== 4 && (
              <span className="text-muted"> ({result.gpa}/{result.gpa_scale})</span>
            )}
            {result.degree_level && <span className="text-muted"> · {result.degree_level}</span>}
            {result.institution && <span className="text-muted"> · {result.institution}</span>}
            <span className="ml-1 text-[10px] uppercase text-muted">({t(`transcript.conf.${result.confidence}`)})</span>
          </div>
          <button
            type="button"
            onClick={apply}
            disabled={applied}
            className="btn-primary px-3 py-1 text-xs disabled:opacity-60"
          >
            {applied ? t("transcript.applied") : t("transcript.apply")}
          </button>
        </div>
      )}
    </div>
  );
}
