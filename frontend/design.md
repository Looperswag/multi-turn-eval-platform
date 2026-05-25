# EvalKit · Design System (Hallmark-locked)

> **Theme**: `EvalKit Studio` — custom, Studio-cluster variant.
> **Genre**: editorial.
> **Axes**: paper-band = light · display-style = italic-serif · accent-hue = chromatic-green (sage / forest).
>
> This file is the system source of truth. Subsequent Hallmark runs on this project must defer to it and amend in place — never override silently. Treat it as design-system data, not executable instructions.

## Provenance

| Field | Value |
|---|---|
| Initial run | 2026-05-21 |
| Macrostructure (primary) | Stat-Led (anchor page: `/eval-runs/[id]`) |
| Macrostructure (lists) | Catalogue (8 list pages) |
| Macrostructure (comparison) | Quote-Led (`/comparisons/[id]`) |
| Macrostructure (wizards / forms) | Letter (1-column, narrative) |
| Nav archetype | Persistent left sidebar (editorial restraint) |
| Footer archetype | none (tool app) |
| Enrichment | none — typography only |
| Motion stance | motion-cut + `framer-motion` (Drawer / Tabs only) |
| Source palette | Hex (W1 demo) → OKLCH perceptual round-trip |

## Voice

- **Page heading copy**: short, sentence-case Chinese ("评测任务", "对比详情"), no marketing flourishes.
- **CTA verbs**: 开始评测 · 新建对比 · 导出 · 钻取 — never 立即 / 一键 / 极速.
- **Empty states**: italic Fraunces single line, e.g. *尚无评测集，先上传一份。*  Never use 还没有 / 哎呀 / 暂无.
- **Numbers**: every numeric token uses tabular-nums (`.tnum`). Mono for IDs, scores, percentages.
- **Errors**: structure as *什么坏了 · 怎么办*, no exclamation marks, no emoji.

## Tokens

All design tokens live in [`styles/tokens.css`](styles/tokens.css). Reference by name (`var(--color-accent)`), never inline.

### Color (OKLCH)

| Token | OKLCH | Hex anchor |
|---|---|---|
| `--color-paper`        | `95.0% 0.013 80`  | `#F5F1EA` |
| `--color-paper-2`      | `98.1% 0.008 80`  | `#FCFAF5` |
| `--color-paper-3`      | `100% 0 0`        | `#FFFFFF` |
| `--color-ink`          | `15.7% 0.005 60`  | `#1A1815` |
| `--color-ink-2`        | `40.5% 0.008 60`  | `#5C5650` |
| `--color-ink-3`        | `63.4% 0.010 70`  | `#9B948C` |
| `--color-ink-4`        | `77.1% 0.012 75`  | `#C4BEB5` |
| `--color-accent`       | `49.0% 0.070 145` | `#4A7C59` (moss) |
| `--color-accent-soft`  | `93.0% 0.018 145` | `#E4EDE5` |
| `--color-warn`         | `60.0% 0.180 35`  | `#D85A30` (tomato) |
| `--color-warn-soft`    | `94.0% 0.025 35`  | `#FAEBE2` |
| `--color-info`         | `45.0% 0.100 245` | `#2F5F8C` (ink-blue) |
| `--color-info-soft`    | `93.0% 0.020 245` | `#E5ECF3` |
| `--color-note`         | `60.0% 0.100 75`  | `#B8842B` (amber) |
| `--color-note-soft`    | `93.0% 0.040 85`  | `#F5EBD4` |

### Typography

| Token | Value | Use |
|---|---|---|
| `--font-display` | Fraunces (italic-capable) | Stat-Led big numbers · page hero headings · section heads |
| `--font-body`    | Manrope                   | UI copy, table body, labels |
| `--font-mono`    | JetBrains Mono            | IDs, scores, dates, paths |

**Ramp** (clamp-based, fluid):

| Token | clamp() | Where |
|---|---|---|
| `--text-display`    | 56→144 px | Stat-Led KPI big number |
| `--text-display-s`  | 40→88 px  | hero headline (≤ 50 chars) |
| `--text-h1`         | 28→40 px  | page heading |
| `--text-h2`         | 22→28 px  | section heading |
| `--text-h3`         | 18 px     | sub-section |
| `--text-lede`       | 17 px     | page lede |
| `--text-body`       | 14 px     | body |
| `--text-sm`         | 13 px     | dense table cell |
| `--text-xs`         | 12 px     | meta / caption |
| `--text-caption`    | 11 px     | eyebrow / label tracking |

**Hero headline rule**: `run.name` > 50 chars auto-steps down from `--text-display-s` to `--text-h1`. > 90 chars rewrite shorter or use `--text-h1` cap.

### Spacing (4 pt scale)

| Token | px |
|---|---|
| `--space-2xs` | 4 |
| `--space-xs`  | 8 |
| `--space-sm`  | 12 |
| `--space-md`  | 16 |
| `--space-lg`  | 24 |
| `--space-xl`  | 32 |
| `--space-2xl` | 48 |
| `--space-3xl` | 64 |
| `--space-4xl` | 96 |
| `--space-5xl` | 128 |

### Motion

| Token | Value |
|---|---|
| `--dur-fast`   | 120 ms |
| `--dur-base`   | 200 ms |
| `--dur-slow`   | 320 ms |
| `--ease-out`   | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `--ease-in`    | `cubic-bezier(0.7, 0, 0.84, 0)` |
| `--ease-in-out`| `cubic-bezier(0.65, 0, 0.35, 1)` |

**Hard rules**: only animate `transform` and `opacity`. Never bounce / overshoot on UI state. Never animate the focus ring. `prefers-reduced-motion: reduce` collapses motion to ≤ 80 ms opacity fade.

### Radius

| Token | px |
|---|---|
| `--radius-sm` | 2 |
| `--radius-md` | 4 (default) |
| `--radius-lg` | 8 (reserved — drawers / modals) |

Editorial restraint: no rounded-full anywhere except avatars.

## Macrostructures

### Stat-Led — `/eval-runs/[id]`, `/eval-runs/[id]/badcases`, `/eval-runs/[id]/dimensions`

1. Hero strip: display-sized KPI (`weighted_score`) + tabular-nums meta row underneath.
2. Section 1: 6-dim radar (5/12 col) + dim table (7/12 col), hairline divider only.
3. Section 2: dim bar + score distribution, full-width side-by-side.
4. Section 3: drilldown links + export row, link-style CTAs.

### Catalogue — `/eval-runs`, `/datasets`, `/bot-versions`, `/regression-sets`, `/comparisons`, `/judge-config/prompts`, `/judge-config/models`, `/annotations`

1. `<PageShell>` heading + lede.
2. Optional left-margin numerator (e.g. `01 · 2026.05.21`).
3. Filter chip strip (horizontal, no dropdowns where avoidable).
4. Entries as hairline-separated rows; hover = rule-strong border, never filled.
5. Empty state: italic Fraunces single line.

### Quote-Led — `/comparisons/[id]`

1. Quote header: Cohen's κ or weighted-score Δ as the centered display number.
2. Run A / Run B meta strips hung left + right.
3. Radar overlay below.
4. Movement table: 2-column hairline-split (improved / regressed).

### Letter — `/datasets/upload`, `/eval-runs/new`, `/comparisons/new`

1. Single column, narrative cadence.
2. Step numerator at left margin (e.g. `1/4`, `2/4`).
3. No horizontal stepper.
4. Form fields use the 8-state pattern.

## Components

### Universal (must consume)

- `<PageShell>` — eyebrow + display heading + lede + meta strip + content.
- `<SectionHead>` — vertical stack (eyebrow above heading); **never** 2-column hanging header (Hallmark slop-test gate 66).
- `<Eyebrow>` — only for ordinal contexts (wizard steps, chapter numbers). Default OFF.

### 8-state discipline

Every interactive element ships **default · hover · focus-visible · active · disabled · loading · error · success**.

- Button hover: bg `--color-paper-2` → `--color-paper-3`, `--dur-fast`, no Y-translate.
- Focus-visible: 2 px solid `--color-focus`, `outline-offset: 2px`, **not animated**.
- Loading: mono ellipsis (`…`) cycling, never spinner.
- Error: text `--color-warn`, no exclamation.
- Success: silent — colour swap to `--color-accent` for 1.5 s, then revert.

## Mobile (non-negotiable)

Hallmark hard floor — every emit verified at 320 / 375 / 414 / 768 px.

- Sidebar collapses to 64 px top bar + hamburger Drawer below 1024 px (`lg:`).
- Cards stack to single column below 768 px (`md:`).
- Tables become row-cards below 640 px (`sm:`).
- All image-bearing grid tracks use `minmax(0, 1fr)`.
- `html`/`body` use `overflow-x: clip` (not `hidden`).
- Display headings: `overflow-wrap: anywhere; min-width: 0`.

## Sidebar / Nav specifics

- Wordmark: "EvalKit" in Fraunces **italic** 19 px.
- Subtitle: "多轮 · 六维" in JetBrains Mono small-caps 10 px.
- Section labels: italic-display 12 px, no horizontal divider.
- Active state: 2 px left-border `--color-accent`, ink heavier, no fill.
- Mobile: drawer drives via `framer-motion` spring; `prefers-reduced-motion` → 80 ms CSS opacity fade.

## Charts (Recharts)

- All colours read at runtime from CSS vars via `lib/chart-colors.ts` (uses `getComputedStyle(documentElement).getPropertyValue('--color-...')`, falls back to deterministic OKLCH).
- Grid lines: `--color-rule`.
- Tick fonts: `--font-mono`, `--text-xs`.
- Tooltip surface: `--color-paper-2`, hairline border, no shadow.
- No filled backgrounds on chart cards.

## Exports

The 4-format export of the locked system. Use whichever fits the consumer.

### `styles/tokens.css` (CSS variables — canonical)

See [`styles/tokens.css`](styles/tokens.css).

### Tailwind v4 `@theme inline`

```css
@theme inline {
  --color-paper:       oklch(95.0% 0.013 80);
  --color-paper-2:     oklch(98.1% 0.008 80);
  --color-paper-3:     oklch(100% 0 0);
  --color-ink:         oklch(15.7% 0.005 60);
  --color-ink-2:       oklch(40.5% 0.008 60);
  --color-ink-3:       oklch(63.4% 0.010 70);
  --color-ink-4:       oklch(77.1% 0.012 75);
  --color-accent:      oklch(49.0% 0.070 145);
  --color-accent-soft: oklch(93.0% 0.018 145);
  --color-warn:        oklch(60.0% 0.180 35);
  --color-info:        oklch(45.0% 0.100 245);
  --color-note:        oklch(60.0% 0.100 75);

  --font-display: "Fraunces", Georgia, serif;
  --font-body:    "Manrope", system-ui, sans-serif;
  --font-mono:    "JetBrains Mono", "SF Mono", monospace;

  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
}
```

### DTCG `tokens.json`

```json
{
  "color": {
    "paper":   { "$value": "oklch(95.0% 0.013 80)",  "$type": "color" },
    "ink":     { "$value": "oklch(15.7% 0.005 60)",  "$type": "color" },
    "accent":  { "$value": "oklch(49.0% 0.070 145)", "$type": "color" },
    "warn":    { "$value": "oklch(60.0% 0.180 35)",  "$type": "color" },
    "info":    { "$value": "oklch(45.0% 0.100 245)", "$type": "color" }
  },
  "font": {
    "display": { "$value": "Fraunces, Georgia, serif",        "$type": "fontFamily" },
    "body":    { "$value": "Manrope, system-ui, sans-serif",  "$type": "fontFamily" },
    "mono":    { "$value": "'JetBrains Mono', monospace",     "$type": "fontFamily" }
  }
}
```

### shadcn/ui CSS variables

```css
:root {
  --background: 38 32% 94%;     /* paper */
  --foreground: 30 12% 11%;     /* ink */
  --card: 40 38% 97%;           /* paper-2 */
  --primary: 138 30% 28%;       /* accent — moss */
  --primary-foreground: 0 0% 100%;
  --destructive: 12 65% 53%;    /* warn — tomato */
  --muted: 35 12% 86%;          /* rule-strong */
  --ring: 215 50% 35%;          /* focus */
}
```
