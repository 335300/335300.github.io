import type { ReactNode } from 'react';
import type { BudgetStatus } from '../../lib/types';
import { budgetKind, StatusText } from './StatusBadge';

/**
 * The track takes this share of the bar area, so spending past the budget
 * (up to about 128 %) still has room to show. Drawing only — no money maths.
 */
const TRACK = 78;

const FILL: Record<BudgetStatus, string> = {
  under: 'bg-positive',
  on_budget: 'bg-positive',
  warning: 'bg-warning',
  over: 'bg-negative',
  unbudgeted: 'bg-neutral-tint border border-line-strong',
};

/**
 * One "budget vs real" row (Style Guide 6). Grey track = the budget; the fill
 * is what was spent, coloured by the status the BACKEND sent: teal within,
 * amber "heads-up" (variable, from 80 %), red only when exceeded. The │ marker
 * is the usual month. Every number and word arrives ready-made; the row only
 * turns the backend's percentages into widths.
 */
export function BudgetBarRow({ label, usedPct, usualPct, status, amount, statusText, noBudgetPct, testId }: {
  /** Category name. */
  label: ReactNode;
  /** Spent as % of the budget (backend `used_pct`); null when there is no budget. */
  usedPct: number | null;
  /** The usual month as % of the budget (backend); omit to hide the │ marker. */
  usualPct?: number | null;
  status: BudgetStatus;
  /** "€312 of €450" — or "€45 spent" when there is no budget. */
  amount: ReactNode;
  /** "On track · €138 left", "Over by €35", "No budget set". */
  statusText: ReactNode;
  /** No-budget rows only: how long to draw the neutral bar (backend share of the largest row), 0–100. */
  noBudgetPct?: number | null;
  testId?: string;
}) {
  const noBudget = status === 'unbudgeted' || usedPct === null;
  const scaled = (pct: number) => `${Math.max(0, Math.min(100, (pct * TRACK) / 100))}%`;
  const fillWidth = noBudget ? scaled(noBudgetPct ?? 0) : scaled(usedPct ?? 0);
  const markerLeft = usualPct !== null && usualPct !== undefined && !noBudget ? scaled(usualPct) : null;
  const kind = budgetKind(noBudget ? 'unbudgeted' : status);

  return (
    <div className="grid min-h-12 grid-cols-[120px_minmax(0,1fr)_210px] items-center gap-4 border-b border-line last:border-b-0" data-testid={testId}>
      <span className="truncate text-[13px] font-medium text-ink">{label}</span>
      <div className="relative h-7" aria-hidden>
        {!noBudget && <div className="absolute left-0 top-2 h-3 rounded bg-track" style={{ width: `${TRACK}%` }} />}
        <div className={`absolute left-0 top-2 box-border h-3 rounded ${FILL[noBudget ? 'unbudgeted' : status]}`} style={{ width: fillWidth }} />
        {markerLeft && (
          <div title="Usual month" className="absolute top-0.5 h-6 w-0.5 rounded-sm bg-ink-muted" style={{ left: markerLeft }} />
        )}
      </div>
      <div className="flex flex-col items-end gap-0.5 text-right">
        <span className="num text-[13px] font-semibold text-ink">{amount}</span>
        <StatusText kind={kind}>{statusText}</StatusText>
      </div>
    </div>
  );
}

/** The legend line for a list of budget rows ("│ usual month"). */
export function BudgetBarLegend({ children = 'usual month' }: { children?: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-label text-ink-muted">
      <span className="inline-block h-3 w-0.5 rounded-sm bg-ink-muted" aria-hidden />
      {children}
    </span>
  );
}
