"use client";

import { useEffect, useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { getOptions } from "@/lib/api";
import { useChartColors } from "@/lib/theme";
import { useI18n } from "@/lib/i18n";

const GEO_URL = "/countries-110m.json";

const norm = (s: string) => s.trim().toLowerCase();

// Map our dataset country names to the world-atlas `name` property where they differ.
const ALIASES: Record<string, string> = {
  czechia: "czech republic",
  turkey: "türkiye",
};
function keysFor(name: string): string[] {
  const n = norm(name);
  return ALIASES[n] ? [n, ALIASES[n]] : [n];
}

/** Interactive world map highlighting countries we cover; click one to pre-fill the wizard. */
export function CountryMap({ onSelect }: { onSelect: (country: string) => void }) {
  const colors = useChartColors();
  const { t } = useI18n();
  const [countries, setCountries] = useState<string[]>([]);
  const [hovered, setHovered] = useState<string | null>(null);

  useEffect(() => {
    getOptions()
      .then((o) => setCountries(o.countries))
      .catch(() => setCountries([]));
  }, []);

  // Normalized lookup: any map name → our canonical dataset name.
  const coveredByName = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of countries) for (const k of keysFor(c)) m.set(k, c);
    return m;
  }, [countries]);

  return (
    <div className="card flex h-full min-h-[420px] flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-border bg-surface-2/60 px-5 py-3.5">
        <div>
          <h3 className="font-display text-sm font-semibold leading-none">{t("map.title")}</h3>
          <p className="mt-1 text-xs text-muted">{t("map.hint")}</p>
        </div>
        <span className="chip border border-primary/30 bg-primary-weak text-primary">
          {countries.length} {t("map.covered")}
        </span>
      </div>

      <div className="relative flex-1">
        <ComposableMap
          projection="geoMercator"
          projectionConfig={{ scale: 110, center: [10, 35] }}
          style={{ width: "100%", height: "100%" }}
        >
          <Geographies geography={GEO_URL}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const name: string = geo.properties.name;
                const canonical = coveredByName.get(norm(name));
                const covered = Boolean(canonical);
                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    onMouseEnter={() => setHovered(covered ? canonical! : null)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => covered && onSelect(canonical!)}
                    style={{
                      default: {
                        fill: covered ? colors.primary : colors.grid,
                        stroke: colors.axis,
                        strokeWidth: 0.3,
                        outline: "none",
                        cursor: covered ? "pointer" : "default",
                        opacity: covered ? 0.9 : 0.5,
                      },
                      hover: {
                        fill: covered ? colors.primary : colors.grid,
                        outline: "none",
                        opacity: covered ? 1 : 0.5,
                      },
                      pressed: { fill: colors.primary, outline: "none" },
                    }}
                  />
                );
              })
            }
          </Geographies>
        </ComposableMap>

        {hovered && (
          <div className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium shadow-sm">
            {hovered}
          </div>
        )}
      </div>

      <div className="flex items-center gap-4 border-t border-border px-5 py-2.5 text-[11px] text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-primary" /> {t("map.legend.covered")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: colors.grid }} /> {t("map.legend.none")}
        </span>
      </div>
    </div>
  );
}
