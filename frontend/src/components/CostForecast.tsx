"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { postForecast, type CandidatePlan, type ForecastResponse } from "@/lib/api";
import { useChartColors } from "@/lib/theme";
import { useI18n } from "@/lib/i18n";

function money(n: number, cur: string) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
}

type ForecastTooltipProps = {
  active?: boolean;
  payload?: { payload: { year_label: string; tuition: number; living: number; total: number } }[];
  cur: string;
  t: (key: string) => string;
};

function ForecastTooltip({ active, payload, cur, t }: ForecastTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{d.year_label}</p>
      <p className="figure mt-0.5 text-xs text-foreground">
        {t("cost.tuition")}: <span className="font-semibold">{money(d.tuition, cur)}</span>
      </p>
      <p className="figure text-xs text-foreground">
        {t("forecast.living")}: <span className="font-semibold">{money(d.living, cur)}</span>
      </p>
      <p className="figure mt-1 border-t border-border pt-1 text-xs font-semibold text-primary">
        {t("cost.total")}: {money(d.total, cur)}
      </p>
    </div>
  );
}

/** Multi-year cost projection for the selected candidate (deterministic backend math). */
export function CostForecast({ c, cur }: { c: CandidatePlan; cur: string }) {
  const colors = useChartColors();
  const { t, locale } = useI18n();
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [commentary, setCommentary] = useState<string | null>(null);
  const [loadingComment, setLoadingComment] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setFailed(false);
    setCommentary(null);
    postForecast({
      country_iso: c.country_iso,
      country_name: c.country_name,
      annual_tuition: c.annual_tuition,
      annual_living: c.annual_living,
      currency: cur,
      years: 4,
    })
      .then((resp) => {
        if (!cancelled) setData(resp);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [c.program_id, c.country_iso, c.country_name, c.annual_tuition, c.annual_living, cur]);

  async function askCommentary() {
    setLoadingComment(true);
    try {
      const resp = await postForecast({
        country_iso: c.country_iso,
        country_name: c.country_name,
        annual_tuition: c.annual_tuition,
        annual_living: c.annual_living,
        currency: cur,
        years: 4,
        with_commentary: true,
        language: locale,
      });
      setCommentary(resp.commentary ?? t("forecast.noCommentary"));
    } catch {
      setCommentary(t("forecast.noCommentary"));
    } finally {
      setLoadingComment(false);
    }
  }

  if (failed || (data && data.series.length === 0)) return null;

  return (
    <div className="card p-4 sm:p-5">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{t("forecast.title")}</h3>
        {data && (
          <span className="chip bg-surface-2 text-muted">
            +{data.assumptions.tuition_inflation_pct}% / +{data.assumptions.living_inflation_pct}%
          </span>
        )}
      </div>
      <p className="mb-4 text-xs text-muted">{t("forecast.hint")}</p>

      {!data ? (
        <div className="h-[220px] animate-pulse rounded-xl bg-surface-2" />
      ) : (
        <>
          <div
            role="img"
            aria-label={`${t("forecast.title")}: ${data.series
              .map((y) => `${y.year_label} ${money(y.total, cur)}`)
              .join("; ")}.`}
          >
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={data.series} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                <CartesianGrid vertical={false} stroke={colors.grid} strokeDasharray="3 3" />
                <XAxis
                  dataKey="year_label"
                  tick={{ fontSize: 11, fill: colors.axis }}
                  tickLine={false}
                  axisLine={{ stroke: colors.grid }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: colors.axis }}
                  tickLine={false}
                  axisLine={false}
                  width={48}
                  domain={["auto", "auto"]}
                  tickFormatter={(v: number) => (v >= 1000 ? `${Math.round(v / 1000)}k` : `${v}`)}
                />
                <Tooltip content={<ForecastTooltip cur={cur} t={t} />} />
                <Line type="monotone" dataKey="total" stroke={colors.primary} strokeWidth={2.5} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="living" stroke="#8B5CF6" strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
                <Line type="monotone" dataKey="tuition" stroke="#3B82F6" strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-muted">
            {t("forecast.assumption")}: {data.assumptions.note}
          </p>

          {commentary ? (
            <div className="mt-3 rounded-xl border border-primary/25 bg-primary-weak/30 p-3 text-sm leading-relaxed">
              {commentary}
              <p className="mt-1.5 text-[10px] text-muted">{t("forecast.aiDisclaimer")}</p>
            </div>
          ) : (
            <button
              onClick={askCommentary}
              disabled={loadingComment}
              className="btn-ghost mt-3 px-3 py-1.5 text-xs"
            >
              {loadingComment ? t("forecast.loading") : t("forecast.askAi")}
            </button>
          )}
        </>
      )}
    </div>
  );
}
