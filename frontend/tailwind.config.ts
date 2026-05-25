import type { Config } from "tailwindcss";

/* Hallmark · tailwind.config.ts · EvalKit Studio
 * All colors / fonts / spacing consume CSS vars from styles/tokens.css.
 * Do not introduce hex values here — break the single-source rule.
 */

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // paper · ink
        paper: "var(--color-paper)",
        "paper-2": "var(--color-paper-2)",
        "paper-3": "var(--color-paper-3)",
        // legacy alias so existing class names (`bg-bg`, `bg-card`) keep working
        bg: "var(--color-paper)",
        card: "var(--color-paper-2)",
        "card-2": "var(--color-paper-3)",
        ink: "var(--color-ink)",
        "ink-2": "var(--color-ink-2)",
        "ink-3": "var(--color-ink-3)",
        "ink-4": "var(--color-ink-4)",
        rule: "var(--color-rule)",
        "rule-strong": "var(--color-rule-strong)",
        // accents (canonical names)
        accent: "var(--color-accent)",
        "accent-soft": "var(--color-accent-soft)",
        warn: "var(--color-warn)",
        "warn-soft": "var(--color-warn-soft)",
        info: "var(--color-info)",
        "info-soft": "var(--color-info-soft)",
        note: "var(--color-note)",
        "note-soft": "var(--color-note-soft)",
        focus: "var(--color-focus)",
        // legacy aliases (moss / tomato / ink-blue / amber) — keep building until full migration in Phase C/D
        moss: "var(--color-accent)",
        "moss-bg": "var(--color-accent-soft)",
        tomato: "var(--color-warn)",
        "tomato-bg": "var(--color-warn-soft)",
        "ink-blue": "var(--color-info)",
        "ink-blue-bg": "var(--color-info-soft)",
        amber: "var(--color-note)",
        "amber-bg": "var(--color-note-soft)",
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      },
      fontSize: {
        // editorial ramp — values drive from tokens.css clamp()s
        display:    ["var(--text-display)",    { lineHeight: "0.95", letterSpacing: "-0.02em" }],
        "display-s":["var(--text-display-s)",  { lineHeight: "1.02", letterSpacing: "-0.015em" }],
        h1:         ["var(--text-h1)",         { lineHeight: "1.15" }],
        h2:         ["var(--text-h2)",         { lineHeight: "1.2"  }],
        h3:         ["var(--text-h3)",         { lineHeight: "1.3"  }],
        lede:       ["var(--text-lede)",       { lineHeight: "1.55" }],
        base:       ["var(--text-body)",       { lineHeight: "1.55" }],
        sm:         ["var(--text-sm)",         { lineHeight: "1.5"  }],
        xs:         ["var(--text-xs)",         { lineHeight: "1.4"  }],
        caption:    ["var(--text-caption)",    { lineHeight: "1.3", letterSpacing: "0.08em" }],
      },
      spacing: {
        "2xs": "var(--space-2xs)",
        xs:    "var(--space-xs)",
        sm:    "var(--space-sm)",
        md:    "var(--space-md)",
        lg:    "var(--space-lg)",
        xl:    "var(--space-xl)",
        "2xl": "var(--space-2xl)",
        "3xl": "var(--space-3xl)",
        "4xl": "var(--space-4xl)",
        "5xl": "var(--space-5xl)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius-md)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
      },
      transitionTimingFunction: {
        out:    "var(--ease-out)",
        in:     "var(--ease-in)",
        "in-out": "var(--ease-in-out)",
      },
      transitionDuration: {
        fast: "var(--dur-fast)",
        DEFAULT: "var(--dur-base)",
        slow: "var(--dur-slow)",
      },
    },
  },
  plugins: [],
};

export default config;
