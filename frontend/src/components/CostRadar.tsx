"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { CandidatePlan } from "@/lib/api";
import { useChartColors } from "@/lib/theme";
import { useI18n } from "@/lib/i18n";

function money(n: number, cur: string) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
}

const SERIES_COLORS = ["#0D9488", "#8B5CF6", "#F59E0B"];
const AXES = ["tuition", "rent", "food", "transport", "total"] as const;

function axisValue(c: CandidatePlan, axis: (typeof AXES)[number]): number {
  if (axis === "tuition") return c.annual_tuition;
  if (axis === "total") return c.total_annual;
  return c.lines.filter((ln) => ln.cost_type === axis).reduce((s, ln) => s + ln.amount, 0);
}

type RadarRow = { axis: string } & Record<string, string | number>;

type RadarTooltipProps = {
  active?: boolean;
  payload?: { dataKey?: string | number; color?: string; payload: RadarRow }[];
  cur: string;
};

function RadarTooltip({ active, payload, cur }: RadarTooltipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{row.axis}</p>
      {payload.map((p) => (
        <p key={String(p.dataKey)} className="figure mt-0.5 text-xs" style={{ color: p.color }}>
          {String(p.dataKey)}:{" "}
          <span className="font-semibold">{money(Number(row[`real_${p.dataKey}`] ?? 0), cur)}</span>
        </p>
      ))}
    </div>
  );
}

/** Radar overlay of pinned candidates, each axis scaled 0–100 against the max option. */
export function CostRadar({ candidates, cur }: { candidates: CandidatePlan[]; cur: string }) {
  const colors = useChartColors();
  const { t } = useI18n();
  if (candidates.length < 2) return null;

  // Short display names must be unique — they double as dataKeys.
  const names = candidates.map((c, i) => {
    const short = c.university_name.split(" ").slice(0, 2).join(" ");
    return candidates.some((o, j) => j !== i && o.university_name.split(" ").slice(0, 2).join(" ") === short)
      ? `${short} (${c.city_name})`
      : short;
  });

  const rows: RadarRow[] = AXES.map((axis) => {
    const values = candidates.map((c) => axisValue(c, axis));
    const max = Math.max(...values);
    const row: RadarRow = { axis: t(`cost.${axis}`) };
    candidates.forEach((c, i) => {
      row[names[i]] = max > 0 ? Math.round((values[i] / max) * 100) : 0;
      row[`real_${names[i]}`] = Math.round(values[i]);
    });
    return row;
  });

  return (
    <div className="border-b border-border px-4 py-4 sm:px-5">
      <h4 className="mb-1 text-sm font-semibold">{t("radar.title")}</h4>
      <p className="mb-2 text-xs text-muted">{t("radar.hint")}</p>
      <p className="mb-1 flex flex-wrap items-center gap-3 text-xs text-muted">
        {names.map((n, i) => (
          <span key={n} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: SERIES_COLORS[i] }} /> {n}
          </span>
        ))}
      </p>
      <div
        role="img"
        aria-label={`${t("radar.title")}: ${names.join(", ")}.`}
      >
        <ResponsiveContainer width="100%" height={280}>
          <RadarChart data={rows} margin={{ top: 12, right: 32, bottom: 12, left: 32 }}>
            <PolarGrid stroke={colors.grid} />
            <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: colors.axis }} />
            <Tooltip content={<RadarTooltip cur={cur} />} />
            {names.map((n, i) => (
              <Radar
                key={n}
                name={n}
                dataKey={n}
                stroke={SERIES_COLORS[i]}
                fill={SERIES_COLORS[i]}
                fillOpacity={0.18}
                strokeWidth={2}
              />
            ))}
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>{t("radar.title")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("radar.axis")}</th>
            {names.map((n) => (
              <th key={n} scope="col">{n}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.axis}>
              <th scope="row">{r.axis}</th>
              {names.map((n) => (
                <td key={n}>{money(Number(r[`real_${n}`] ?? 0), cur)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
