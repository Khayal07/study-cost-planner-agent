"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

type Theme = "light" | "dark";
const STORAGE_KEY = "scp-theme";

type ThemeCtx = { theme: Theme; toggle: () => void; setTheme: (t: Theme) => void };
const Ctx = createContext<ThemeCtx | null>(null);

/**
 * Inline script (runs before paint) that resolves the saved/system theme and sets
 * the `dark` class on <html>, preventing a flash of the wrong theme. Injected via
 * dangerouslySetInnerHTML in the layout <head>.
 */
export const themeInitScript = `
(function(){
  try {
    var k = "${STORAGE_KEY}";
    var saved = localStorage.getItem(k);
    var sys = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var dark = saved ? saved === "dark" : sys;
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
  } catch (e) {}
})();
`;

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");

  // Sync React state with whatever the init script already applied.
  useEffect(() => {
    const isDark = document.documentElement.classList.contains("dark");
    setThemeState(isDark ? "dark" : "light");
  }, []);

  // Follow OS changes only when the user hasn't made an explicit choice.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      if (!localStorage.getItem(STORAGE_KEY)) apply(e.matches ? "dark" : "light");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const apply = useCallback((t: Theme) => {
    document.documentElement.classList.toggle("dark", t === "dark");
    document.documentElement.style.colorScheme = t;
    setThemeState(t);
  }, []);

  const setTheme = useCallback(
    (t: Theme) => {
      localStorage.setItem(STORAGE_KEY, t);
      apply(t);
    },
    [apply],
  );

  const toggle = useCallback(
    () => setTheme(theme === "dark" ? "light" : "dark"),
    [theme, setTheme],
  );

  return <Ctx.Provider value={{ theme, toggle, setTheme }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

/** Concrete hex values for non-CSS consumers (Recharts) that can't read classes. */
export function useChartColors() {
  const { theme } = useTheme();
  return theme === "dark"
    ? {
        primary: "#14B8A6",
        muted: "#3a4658",
        grid: "#232b38",
        axis: "#93a0b2",
        tooltipBg: "#11161f",
        tooltipBorder: "#232b38",
        text: "#e5e9f0",
      }
    : {
        primary: "#0D9488",
        muted: "#cdd5df",
        grid: "#eaedf1",
        axis: "#5a6472",
        tooltipBg: "#ffffff",
        tooltipBorder: "#e2e6eb",
        text: "#0b1220",
      };
}
