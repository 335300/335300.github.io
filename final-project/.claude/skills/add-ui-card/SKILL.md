---
name: add-ui-card
description: Recipe to build or change a screen, card, table or chart in the Personal Centwise React app - plan, check the API already sends every number, reuse Card/KpiTile/StatusBadge/ProgressBar/MonthGrid, semantic colours, format-only JavaScript (no money maths), TanStack Query hooks, Personal vs Joint wording, then type check, an e2e check and screenshots. Use whenever a task adds or changes anything the user sees.
---

# Add or change a UI card

Load first: `centwise-project-rules`, `centwise-architecture-map`,
`centwise-design-system`, `centwise-money-vocabulary`.

## 1. Plan (wait for OK)

- Which tab and where on it (above/below which card); Personal, Joint or both.
- Which endpoint gives the numbers, and **which fields**. List them.
- If a number is missing from the API → it must be added in Python first
  (`add-backend-feature`). Never compute it in TypeScript.
- How it folds (`collapseKey`) if it is a big block.
- Which e2e check you will add.

**Stop and wait for Josue's OK.**

## 2. Build

- Files: `frontend/src/pages/<tab>/<Name>.tsx` (or `components/charts/`).
- Data: a hook in `api/queries.ts` (`useQuery` with a clear key; mutations call
  `invalidateQueries()` so every tab refreshes). Types in `lib/types.ts`.
- Layout: `Card` (title, action), `KpiTile`, badges with icon + word,
  `ProgressBar` with a label, `EmptyState` when there is no data.
- Colours: tokens only (`text-positive`, `bg-secondary-tint`, `color('invest')`
  in charts). No hex, no hue names.
- Numbers: `fmtMoney` / `fmtSigned` / `fmtPct` + class `num`.
- **Allowed in TS:** formatting, sorting/filtering rows for display, choosing a
  tone from a status the API sent. **Not allowed:** adding, subtracting,
  averaging, percentages or rounding of money.
- Text: Personal = no explanatory grey paragraphs; Joint = plain English for Isa.
- Give elements a stable `data-testid` or an accessible label so e2e can find them.
- Form fields: unique ids (`idPrefix` pattern, like `TransactionForm`).

## 3. Check

1. `cd frontend && npm run typecheck` (the hook runs it after each edit too).
2. Add or update a `check('…')` in `frontend/scripts/e2e.mjs` that creates the
   data through the UI and asserts the card shows it.
3. Run the `ui-check` skill (build + e2e on a throwaway folder + screenshots).
4. Look at the screenshots yourself (Read the PNG). Check: nothing cut off,
   numbers line up, statuses have words, fold works, Joint wording plain.
5. Update `AI output/2026-11-16-app-screens-guide.md` (what the card does).
6. Ask the `ui-reviewer` for an independent look.

## 4. Finish

- `write-memory-entry` (include e2e result, e.g. "e2e.mjs 43/43, console clean").
- Installing: `./build-app.sh --fast --install` for frontend-only changes —
  **ask Josue first**.
