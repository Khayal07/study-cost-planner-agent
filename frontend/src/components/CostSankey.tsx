"use client";

import { Layer, Rectangle, ResponsiveContainer, Sankey, Tooltip } from "recharts";
import type { CandidatePlan } from "@/lib/api";
import { useChartColors } from "@/lib/theme";
import { useI18n } from "@/lib/i18n";

function money(n: number, cur: string) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
}

// Fixed palette per cost category — readable on both themes.
export const COST_COLORS: Record<string, string> = {
  tuition: "#0D9488",
  rent: "#3B82F6",
  food: "#F59E0B",
  transport: "#8B5CF6",
  insurance: "#06B6D4",
  visa: "#F43F5E",
  utilities: "#84CC16",
  hidden_misc: "#64748B",
};

type SankeyNodeDatum = { name: string; value: number; color: string };

type NodeProps = {
  x: number;
  y: number;
  width: number;
  height: number;
  index: number;
  payload: SankeyNodeDatum & { value: number };
  containerWidth: number;
  textColor: string;
  cur: string;
};

function SankeyNode({ x, y, width, height, payload, containerWidth, textColor, cur }: NodeProps) {
  const isRight = x + width > containerWidth / 2;
  const tx = isRight ? x - 6 : x + width + 6;
  return (
    <Layer>
      <Rectangle x={x} y={y} width={width} height={height} fill={payload.color} fillOpacity={0.9} radius={2} />
      <text
        x={tx}
        y={y + height / 2}
        textAnchor={isRight ? "end" : "start"}
        dominantBaseline="middle"
        fontSize={11}
        fill={textColor}
      >
        {payload.name}
        <tspan fontSize={10} fillOpacity={0.7}>
          {"  "}{money(payload.value, cur)}
        </tspan>
      </text>
    </Layer>
  );
}

type SankeyTooltipProps = {
  active?: boolean;
  payload?: { payload: { payload?: SankeyNodeDatum; value?: number; target?: SankeyNodeDatum } }[];
  cur: string;
};

function SankeyTooltip({ active, payload, cur }: SankeyTooltipProps) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  // Node hover carries the datum directly; link hover carries source/target nodes.
  const name = p.payload?.name ?? p.target?.name;
  const value = p.payload?.value ?? p.value;
  if (!name || value == null) return null;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{name}</p>
      <p className="figure mt-0.5 text-sm font-semibold text-foreground">{money(value, cur)}/yr</p>
    </div>
  );
}

/** Sankey flow: annual total → cost categories, from the candidate's cost lines. */
export function CostSankey({ c, cur }: { c: CandidatePlan; cur: string }) {
  const colors = useChartColors();
  const { t } = useI18n();

  const byType = new Map<string, number>();
  for (const ln of c.lines) {
    if (ln.amount > 0) byType.set(ln.cost_type, (byType.get(ln.cost_type) ?? 0) + ln.amount);
  }
  const cats = [...byType.entries()].sort((a, b) => b[1] - a[1]);
  if (cats.length < 2) return null;

  const total = cats.reduce((s, [, v]) => s + v, 0);
  const nodes: SankeyNodeDatum[] = [
    { name: t("sankey.total"), value: total, color: colors.primary },
    ...cats.map(([type, value]) => ({
      name: t(`cost.${type}`),
      value,
      color: COST_COLORS[type] ?? colors.muted,
    })),
  ];
  const links = cats.map(([, value], i) => ({ source: 0, target: i + 1, value }));

  return (
    <div className="card p-4 sm:p-5">
      <h3 className="mb-1 text-sm font-semibold">{t("sankey.title")}</h3>
      <p className="mb-3 text-xs text-muted">
        {c.university_name} · {money(total, cur)}/yr
      </p>
      <div
        role="img"
        aria-label={`${t("sankey.title")}: ${cats
          .map(([type, v]) => `${t(`cost.${type}`)} ${money(v, cur)}`)
          .join("; ")}.`}
      >
        <ResponsiveContainer width="100%" height={Math.max(220, cats.length * 44)}>
          <Sankey
            data={{ nodes, links }}
            nodeWidth={10}
            nodePadding={28}
            margin={{ top: 8, right: 185, bottom: 8, left: 8 }}
            link={{ stroke: colors.muted, strokeOpacity: 0.35 }}
            node={(props: Omit<NodeProps, "textColor" | "cur">) => (
              <SankeyNode {...props} textColor={colors.text} cur={cur} />
            )}
          >
            <Tooltip content={<SankeyTooltip cur={cur} />} />
          </Sankey>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>{t("sankey.title")}</caption>
        <tbody>
          {cats.map(([type, v]) => (
            <tr key={type}>
              <th scope="row">{t(`cost.${type}`)}</th>
              <td>{money(v, cur)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
