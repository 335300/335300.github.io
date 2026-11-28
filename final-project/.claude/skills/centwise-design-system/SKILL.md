---
name: centwise-design-system
description: Personal Centwise look and feel - semantic colour tokens and what each colour means (blue, savings teal, asset violet, gold for celebrations only), Tailwind classes, shared components (Card with fold, KpiTile, StatusBadge, ProgressBar, MonthGrid, Modal, TooltipCard), chart rules for Recharts, money formatting, accessibility (never colour alone) and the UI writing rules for Personal vs Joint screens. Use when building, changing or reviewing any screen, card, chart or UI text in the app.
---

# Centwise design system

## Colours: semantic tokens only

Defined as RGB channels in `frontend/src/index.css` (`--c-*`) and mapped in
`frontend/tailwind.config.js`. **Code never uses a hex value or a hue name**
(no `text-red-500`, no `#24508F`). Charts get colours from
`lib/theme.ts → color('token')` because SVG cannot read CSS variables.

| Token (Tailwind) | Colour | Means |
|---|---|---|
| `primary` | Centwise Blue #24508F | main actions, selected state, brand |
| `secondary` | Savings Teal #0F766E | savings, "within budget", on track |
| `invest` | Asset Violet #7C4DBE | money that builds an asset (investments) |
| `gold` | Milestone Gold #F2C14E | **celebration only, never text** |
| `positive` | green #15803D | good number (kept, cash in) |
| `negative` | red #B42318 | bad number, over budget, overdue |
| `warning` | amber #B45309 | heads-up (≥ 80 % used), behind |
| `ink` / `ink-soft` / `ink-muted` | text greys | main / secondary / quiet text (muted passes AA) |
| `surface`, `bg`, `line` | white, page grey, borders | layout |
| `logo` | violet #6D28D9 | **the logo only** |

Each colour has a `-tint` (pale background) for badges and selected rows.

## Shared components (reuse before creating)

| Component | File | Use for |
|---|---|---|
| `Card` | `components/ui/Card.tsx` | every block; `title`, `subtitle`, `action`; add `collapseKey` + `collapseLabel` to make it foldable (state remembered per viewer) |
| `EmptyState`, `Hint` | `Card.tsx` | empty cards; small notes |
| `KpiTile` | `components/ui/KpiTile.tsx` | one headline number; `tone` = neutral / positive / negative / brand; `meta` line carries meaning, not only colour |
| `BudgetBadge`, `GoalBadge` | `components/ui/StatusBadge.tsx` | statuses — always **icon + word** |
| `ProgressBar` | `components/ui/ProgressBar.tsx` | progress; tones secondary/warning/negative/positive/neutral/primary/invest; give a `label` |
| `MonthGrid`, `MonthNav` | `components/ui/MonthGrid.tsx` | month calendars (Transactions, Bills & goals) |
| `Modal` | `components/ui/Modal.tsx` | dialogs (`title`, `footer`, `width`) |
| `FoldButton` | `components/ui/FoldButton.tsx` | fold arrow with `aria-expanded` |
| `ErrorNote`, `Loading` | `components/ui/Feedback.tsx` | errors and loading |
| `TooltipCard` | `components/charts/ChartTooltip.tsx` | every chart hover card |

Classes: `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.input`, `.label`,
and `.num` (tabular numerals) on **every money value** so columns line up.
Icons: `lucide-react`.

## Money and dates on screen

- Format with `lib/format.ts` only: `fmtMoney`, `fmtSigned`, `fmtExpense`,
  `fmtPct`, `fmtAxis`, `fmtDate`, `fmtMonthYear`, `fmtLocal` (PYG).
  Negative numbers use a real minus sign (−).
- **Formatting is allowed in JavaScript; arithmetic is not.** No sums,
  differences, averages, percentages or rounding of money in TS/TSX
  (`reduce`, `a - b`, `x / total * 100` on amounts are red flags). If the
  screen needs a new figure, the backend must send it (see `add-backend-feature`).
- Parsing what the user types (`parseAmount`, `parseLocalAmount`) is allowed.

## Charts (Recharts)

- Colours from `color('token')`, matching the meaning table above
  (cash in = positive, costs = negative/ink, investments = invest, savings = secondary).
- Use `TooltipCard` for hover cards; values formatted with `fmtMoney`.
- Axis labels with `fmtAxis`; no chart without a title or a clear card title.
- Planned / forecast values: dashed lines; real values: solid.
- A flag marker = a goal is bought that month.
- Keep charts readable at 1360 px wide (the e2e viewport).

## Accessibility

- Never colour alone: every status has an icon **and** a word (WCAG 1.4.1).
- Buttons that are only icons need an `aria-label`.
- Text uses `ink`/`ink-soft`/`ink-muted` on `surface`/`bg` (AA contrast);
  never gold text.
- Fold buttons expose `aria-expanded`.

## Writing rules

- **Personal screens:** no grey help paragraphs or subtitles that explain the
  screen. Keep numbers, data lines (e.g. "€X invested in November"), warnings,
  empty-card messages and notes about edits that reach the other profile.
  Explanations live in `AI output/2026-11-16-app-screens-guide.md` — update it
  when a screen changes.
- **Joint screens (for Isa):** plain English, short sentences, a one-line
  explanation is OK. No jargon ("liquidity" → "free to use").
- Use the words from `centwise-money-vocabulary` exactly.
- Symbols already in use: 🛡 essential, § tax-relevant, calendar icon = follows
  income calendar, building icon = follows investment plan, people icon =
  follows Joint plan, flag = goal bought, "linked" = half of a Transfer to Joint.

## Layout

- Page width max 1280 px, `px-6`, cards in a grid; two related cards side by
  side at half width each (e.g. "Where your income went" + "Investments").
- Progressive disclosure: headline tiles first, details lower or folded.
- The calculator button sits bottom-right on every tab; don't cover it.
