"use client";

import { useRef, useState } from "react";
import { toPng } from "html-to-image";
import type { CandidatePlan } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { COST_COLORS } from "./CostSankey";

function money(n: number, cur: string) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
}

function slug(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

/**
 * Wrapped-style shareable summary card. Rendered at 360×450 CSS px and captured
 * at pixelRatio 3 → a 1080×1350 PNG (4:5, social-friendly). Styles are inline
 * hex (theme-independent) and no remote assets are used, so rasterization is
 * deterministic.
 */
export function ShareCard({ c, cur, onClose }: { c: CandidatePlan; cur: string; onClose: () => void }) {
  const { t } = useI18n();
  const cardRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const canShare =
    typeof navigator !== "undefined" && "share" in navigator && "canShare" in navigator;

  const topLines = [...c.lines].sort((a, b) => b.amount - a.amount).slice(0, 3);
  const maxLine = topLines[0]?.amount ?? 1;

  async function capture(): Promise<Blob | null> {
    if (!cardRef.current) return null;
    const dataUrl = await toPng(cardRef.current, { pixelRatio: 3, cacheBust: true });
    const res = await fetch(dataUrl);
    return res.blob();
  }

  async function download() {
    setBusy(true);
    try {
      const blob = await capture();
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `study-cost-${slug(c.university_name)}.png`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(false);
    }
  }

  async function share() {
    setBusy(true);
    try {
      const blob = await capture();
      if (!blob) return;
      const file = new File([blob], `study-cost-${slug(c.university_name)}.png`, {
        type: "image/png",
      });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: "Study Cost Planner" });
      } else {
        await download();
      }
    } catch {
      /* user cancelled the share sheet — nothing to do */
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t("share.title")}
      onClick={onClose}
    >
      <div
        className="flex max-h-full flex-col items-center gap-3 overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* The captured node — fixed size, inline styles only */}
        <div
          ref={cardRef}
          style={{
            width: 360,
            height: 450,
            background: "linear-gradient(160deg, #0b1220 0%, #123a36 55%, #0D9488 130%)",
            borderRadius: 24,
            padding: 28,
            color: "#e5e9f0",
            display: "flex",
            flexDirection: "column",
            fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
          }}
        >
          <div style={{ fontSize: 11, letterSpacing: 2, textTransform: "uppercase", color: "#5eead4" }}>
            {t("share.tagline")}
          </div>
          <div style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.15, marginTop: 14 }}>
            {c.university_name}
          </div>
          <div style={{ fontSize: 13, color: "#93a0b2", marginTop: 4 }}>
            {c.city_name}, {c.country_name} · {c.program_name}
          </div>

          <div style={{ marginTop: 26 }}>
            <div style={{ fontSize: 12, color: "#93a0b2" }}>{t("share.totalLabel")}</div>
            <div style={{ fontSize: 38, fontWeight: 700, color: "#5eead4", lineHeight: 1.1 }}>
              {money(c.total_annual, cur)}
            </div>
            {c.total_scholarship_value > 0 && c.net_total_annual != null && (
              <div style={{ fontSize: 13, color: "#fbbf24", marginTop: 4 }}>
                {t("share.afterAid")}: {money(c.net_total_annual, cur)}
              </div>
            )}
          </div>

          <div style={{ marginTop: 26, display: "flex", flexDirection: "column", gap: 10 }}>
            {topLines.map((ln) => (
              <div key={ln.cost_type}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                  <span>{t(`cost.${ln.cost_type}`)}</span>
                  <span style={{ fontWeight: 600 }}>{money(ln.amount, cur)}</span>
                </div>
                <div style={{ height: 7, borderRadius: 4, background: "rgba(255,255,255,0.12)" }}>
                  <div
                    style={{
                      height: "100%",
                      borderRadius: 4,
                      width: `${Math.max(6, (ln.amount / maxLine) * 100)}%`,
                      background: COST_COLORS[ln.cost_type] ?? "#5eead4",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div
            style={{
              marginTop: "auto",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: 11,
              color: "#93a0b2",
            }}
          >
            <span style={{ fontWeight: 600, color: "#e5e9f0" }}>Study Cost Planner</span>
            <span>{t("share.footer")}</span>
          </div>
        </div>

        <div className="flex gap-2">
          <button onClick={download} disabled={busy} className="btn-primary px-4 py-2 text-sm">
            {busy ? "…" : t("share.download")}
          </button>
          {canShare && (
            <button onClick={share} disabled={busy} className="btn-ghost bg-surface px-4 py-2 text-sm">
              {t("share.share")}
            </button>
          )}
          <button onClick={onClose} className="btn-ghost bg-surface px-4 py-2 text-sm">
            {t("share.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
