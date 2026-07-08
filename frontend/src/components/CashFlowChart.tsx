"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CandidatePlan } from "@/lib/api";
import { useChartColors } from "@/lib/theme";
import { useI18n } from "@/lib/i18n";

function money(n: number, cur: string) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
}

const MAX_MONTHS = 36;

type MonthDatum = {
  month: number;
  living: number;
  tuition: number;
  oneTime: number;
  cumulative: number;
};

function buildMonths(c: CandidatePlan): MonthDatum[] {
  const programMonths = Math.max(12, Math.round(c.duration_years * 12));
  const months = Math.min(programMonths, MAX_MONTHS);
  // hidden_misc is an annual figure — spread it evenly like living costs.
  const monthlyBase = c.monthly_living + c.annual_hidden / 12;
  const rows: MonthDatum[] = [];
  let cumulative = 0;
  for (let m = 0; m < months; m++) {
    const tuition = m % 6 === 0 && m < programMonths ? c.annual_tuition / 2 : 0;
    const oneTime = m === 0 ? c.annual_one_time : 0;
    cumulative += monthlyBase + tuition + oneTime;
    rows.push({
      month: m + 1,
      living: Math.round(monthlyBase),
      tuition: Math.round(tuition),
      oneTime: Math.round(oneTime),
      cumulative: Math.round(cumulative),
    });
  }
  return rows;
}

type CashTooltipProps = {
  active?: boolean;
  payload?: { payload: MonthDatum }[];
  cur: string;
  t: (key: string) => string;
};

function CashTooltip({ active, payload, cur, t }: CashTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const rows: [string, number][] = [
    [t("cost.tuition"), d.tuition],
    [t("cashflow.oneTime"), d.oneTime],
    [t("cashflow.living"), d.living],
  ];
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">
        {t("cashflow.month")} {d.month}
      </p>
      {rows
        .filter(([, v]) => v > 0)
        .map(([label, v]) => (
          <p key={label} className="figure mt-0.5 text-xs text-foreground">
            {label}: <span className="font-semibold">{money(v, cur)}</span>
          </p>
        ))}
      <p className="figure mt-1 border-t border-border pt-1 text-xs font-semibold text-primary">
        {t("cashflow.cumulative")}: {money(d.cumulative, cur)}
      </p>
    </div>
  );
}

/** Projected month-by-month spend: living every month, tuition per semester, one-time at start. */
export function CashFlowChart({ c, cur }: { c: CandidatePlan; cur: string }) {
  const colors = useChartColors();
  const { t } = useI18n();
  const data = buildMonths(c);
  if (data.length === 0) return null;
  const totalShown = data[data.length - 1].cumulative;

  const legend: { label: string; color: string }[] = [
    { label: t("cost.tuition"), color: "#3B82F6" },
    { label: t("cashflow.oneTime"), color: "#F59E0B" },
    { label: t("cashflow.living"), color: colors.primary },
  ];

  return (
    <div className="card p-4 sm:p-5">
      <h3 className="mb-1 text-sm font-semibold">{t("cashflow.title")}</h3>
      <p className="mb-3 text-xs text-muted">{t("cashflow.hint")}</p>
      <p className="mb-4 flex flex-wrap items-center gap-3 text-xs text-muted">
        {legend.map((l) => (
          <span key={l.label} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: l.color }} /> {l.label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-3.5 rounded-full" style={{ background: "#8B5CF6" }} /> {t("cashflow.cumulative")}
        </span>
      </p>
      <div
        role="img"
        aria-label={`${t("cashflow.title")}: ${data.length} ${t("cashflow.month").toLowerCase()}, ${t(
          "cashflow.cumulative",
        )} ${money(totalShown, cur)}.`}
      >
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid vertical={false} stroke={colors.grid} strokeDasharray="3 3" />
            <XAxis
              dataKey="month"
              tick={{ fontSize: 10, fill: colors.axis }}
              interval={data.length > 24 ? 2 : 1}
              tickLine={false}
              axisLine={{ stroke: colors.grid }}
            />
            <YAxis
              yAxisId="monthly"
              tick={{ fontSize: 11, fill: colors.axis }}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => (v >= 1000 ? `${Math.round(v / 1000)}k` : `${v}`)}
            />
            <YAxis
              yAxisId="cumulative"
              orientation="right"
              tick={{ fontSize: 11, fill: colors.axis }}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => (v >= 1000 ? `${Math.round(v / 1000)}k` : `${v}`)}
            />
            <Tooltip cursor={{ fill: colors.primary, fillOpacity: 0.06 }} content={<CashTooltip cur={cur} t={t} />} />
            <Bar yAxisId="monthly" dataKey="living" stackId="m" fill={colors.primary} fillOpacity={0.75} maxBarSize={20} />
            <Bar yAxisId="monthly" dataKey="oneTime" stackId="m" fill="#F59E0B" fillOpacity={0.85} maxBarSize={20} />
            <Bar yAxisId="monthly" dataKey="tuition" stackId="m" fill="#3B82F6" fillOpacity={0.85} maxBarSize={20} radius={[4, 4, 0, 0]} />
            <Line
              yAxisId="cumulative"
              type="monotone"
              dataKey="cumulative"
              stroke="#8B5CF6"
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>{t("cashflow.title")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("cashflow.month")}</th>
            <th scope="col">{t("cashflow.cumulative")} ({cur})</th>
          </tr>
        </thead>
        <tbody>
          {data
            .filter((d) => d.month % 6 === 0 || d.month === 1)
            .map((d) => (
              <tr key={d.month}>
                <th scope="row">{d.month}</th>
                <td>{money(d.cumulative, cur)}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
