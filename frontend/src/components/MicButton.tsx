"use client";

import { useEffect, useRef, useState } from "react";
import { transcribeAudio } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const MAX_SECONDS = 90;

type MicState = "idle" | "recording" | "transcribing";

/** Push-to-talk mic: records via MediaRecorder, sends to /chat/transcribe and
 * hands the text back (into the input for review — never auto-sent). Renders
 * nothing when the browser lacks MediaRecorder/getUserMedia. */
export function MicButton({
  onTranscript,
  disabled = false,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const { t, locale } = useI18n();
  const [state, setState] = useState<MicState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [supported, setSupported] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Errors are transient toasts — clear after a few seconds.
  useEffect(() => {
    if (!error) return;
    const id = setTimeout(() => setError(null), 4000);
    return () => clearTimeout(id);
  }, [error]);

  useEffect(() => {
    setSupported(
      typeof window !== "undefined" &&
        "MediaRecorder" in window &&
        Boolean(navigator.mediaDevices?.getUserMedia),
    );
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      recorderRef.current?.stream.getTracks().forEach((tr) => tr.stop());
    };
  }, []);

  async function start() {
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError(t("voice.denied"));
      return;
    }
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : undefined;
    const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    recorder.onstop = async () => {
      stream.getTracks().forEach((tr) => tr.stop());
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      if (blob.size === 0) {
        setState("idle");
        return;
      }
      setState("transcribing");
      try {
        const res = await transcribeAudio(blob, locale);
        if (res.limited) setError(t("voice.limited"));
        else if (res.text) onTranscript(res.text);
        else setError(t("voice.empty"));
      } catch (e) {
        setError(e instanceof Error ? e.message : t("voice.error"));
      } finally {
        setState("idle");
      }
    };
    recorderRef.current = recorder;
    recorder.start();
    setState("recording");
    timerRef.current = setTimeout(() => stop(), MAX_SECONDS * 1000);
  }

  function stop() {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  if (!supported) return null;

  return (
    <div className="relative flex items-center">
      <button
        type="button"
        onClick={state === "recording" ? stop : state === "idle" ? start : undefined}
        disabled={disabled || state === "transcribing"}
        aria-label={state === "recording" ? t("voice.stop") : t("voice.start")}
        title={state === "recording" ? t("voice.stop") : t("voice.start")}
        className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl border transition-all disabled:pointer-events-none disabled:opacity-45 ${
          state === "recording"
            ? "border-danger bg-danger/10 text-danger animate-pulse"
            : "border-border bg-surface text-muted hover:border-primary/40 hover:text-primary"
        }`}
      >
        {state === "transcribing" ? (
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4Z" />
          </svg>
        ) : state === "recording" ? (
          <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="9" y="2" width="6" height="12" rx="3" />
            <path d="M5 10v1a7 7 0 0 0 14 0v-1M12 18v4M8 22h8" />
          </svg>
        )}
      </button>
      {error && (
        <span
          role="status"
          className="absolute bottom-11 right-0 w-max max-w-[240px] rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[11px] text-danger shadow-lg"
        >
          {error}
        </span>
      )}
    </div>
  );
}
