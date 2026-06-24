import type { Config } from "tailwindcss";

/**
 * Semantic, theme-aware design tokens.
 * Every color is an RGB triple exposed as a CSS variable (see globals.css) so the
 * same Tailwind class works in light and dark — dark mode simply flips the vars.
 * The `<alpha-value>` placeholder keeps opacity utilities (e.g. bg-primary/10) working.
 */
const withAlpha = (v: string) => `rgb(var(${v}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: withAlpha("--background"),
        surface: withAlpha("--surface"),
        "surface-2": withAlpha("--surface-2"),
        foreground: withAlpha("--foreground"),
        muted: withAlpha("--muted"),
        border: withAlpha("--border"),
        ring: withAlpha("--ring"),
        primary: {
          DEFAULT: withAlpha("--primary"),
          fg: withAlpha("--primary-fg"),
          weak: withAlpha("--primary-weak"),
        },
        accent: {
          DEFAULT: withAlpha("--accent"),
          weak: withAlpha("--accent-weak"),
        },
        success: withAlpha("--success"),
        warning: withAlpha("--warning"),
        danger: withAlpha("--danger"),
        // Back-compat alias so any stray `brand` class still resolves.
        brand: { DEFAULT: withAlpha("--primary"), dark: withAlpha("--primary") },
        ink: withAlpha("--foreground"),
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "var(--font-inter)", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        lg: "0.625rem",
        xl: "0.875rem",
        "2xl": "1.125rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        xs: "0 1px 2px 0 rgb(var(--shadow-color) / 0.04)",
        sm: "0 1px 3px 0 rgb(var(--shadow-color) / 0.07), 0 1px 2px -1px rgb(var(--shadow-color) / 0.06)",
        md: "0 4px 12px -2px rgb(var(--shadow-color) / 0.10), 0 2px 6px -2px rgb(var(--shadow-color) / 0.06)",
        lg: "0 12px 30px -8px rgb(var(--shadow-color) / 0.16), 0 4px 10px -4px rgb(var(--shadow-color) / 0.08)",
        glow: "0 0 0 1px rgb(var(--primary) / 0.20), 0 8px 28px -6px rgb(var(--primary) / 0.30)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.97)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgb(var(--primary) / 0.35)" },
          "70%": { boxShadow: "0 0 0 6px rgb(var(--primary) / 0)" },
          "100%": { boxShadow: "0 0 0 0 rgb(var(--primary) / 0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.4s ease both",
        "fade-up": "fade-up 0.5s cubic-bezier(0.16,1,0.3,1) both",
        "scale-in": "scale-in 0.35s cubic-bezier(0.16,1,0.3,1) both",
        shimmer: "shimmer 1.6s infinite",
        "pulse-ring": "pulse-ring 2s ease-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
