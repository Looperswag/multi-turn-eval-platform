import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F5F1EA",
        card: "#FCFAF5",
        "card-2": "#FFFFFF",
        ink: "#1A1815",
        "ink-2": "#5C5650",
        "ink-3": "#9B948C",
        "ink-4": "#C4BEB5",
        rule: "rgba(26, 24, 21, 0.10)",
        "rule-strong": "rgba(26, 24, 21, 0.20)",
        tomato: "#D85A30",
        "tomato-bg": "#FAEBE2",
        moss: "#4A7C59",
        "moss-bg": "#E4EDE5",
        "ink-blue": "#2F5F8C",
        "ink-blue-bg": "#E5ECF3",
        amber: "#B8842B",
        "amber-bg": "#F5EBD4",
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        body: ["Manrope", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "SF Mono", "Consolas", "monospace"],
      },
      fontSize: {
        xs: ["11px", "1.5"],
        sm: ["13px", "1.5"],
        base: ["14px", "1.5"],
      },
    },
  },
  plugins: [],
};

export default config;
