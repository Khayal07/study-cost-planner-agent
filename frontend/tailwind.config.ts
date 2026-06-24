import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Calm, finance-friendly palette
        brand: {
          DEFAULT: "#1f6feb",
          dark: "#1a4fa0",
        },
        ink: "#0f172a",
        muted: "#64748b",
      },
    },
  },
  plugins: [],
};

export default config;
