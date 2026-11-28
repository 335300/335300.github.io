import type { ReactNode } from 'react';
import { StatusIcon } from './StatusBadge';

export type BarTone = 'secondary' | 'warning' | 'negative' | 'positive' | 'neutral' | 'primary' | 'invest' | 'gold';

const fill: Record<BarTone, string> = {
  secondary: 'bg-secondary',
  warning: 'bg-warning',
  negative: 'bg-negative',
  positive: 'bg-positive',
  neutral: 'bg-ink-muted/50',
  primary: 'bg-primary',
  invest: 'bg-invest',
  gold: 'bg-gold',
};

/**
 * A plain CSS bar on the grey track. `pct` is a share the backend already
 * computed (0–100); it is only clamped to fit the bar.
 */
export function ProgressBar({ pct, tone = 'secondary', height = 'h-2', label, reached = false }: {
  pct: number;
  tone?: BarTone;
  height?: string;
  /** Accessible name ("Laptop progress"). */
  label?: string;
  /** A reached goal: gold fill (celebration only). */
  reached?: boolean;
}) {
  const width = Math.max(0, Math.min(100, pct));
  return (
    <div
      className={`w-full overflow-hidden rounded-pill bg-track ${height}`}
      role="progressbar"
      aria-valuenow={Math.round(width)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div className={`${height} rounded-pill ${fill[reached ? 'gold' : tone]}`} style={{ width: `${width}%` }} />
    </div>
  );
}

/**
 * One savings goal (Style Guide 5): name and "€6,400 of €9,000" on top, the bar,
 * then a note and the percentage. Teal while saving; gold with ★ once reached.
 * Every figure arrives formatted; `pct` is the backend's share.
 */
export function GoalProgress({ name, amount, pct, pctLabel, note, reached = false, testId }: {
  name: ReactNode;
  /** "€6,400 of €9,000" */
  amount: ReactNode;
  pct: number;
  /** "71%" (fmtPct of the backend share). */
  pctLabel: string;
  /** "About 9 months to go" / "Goal reached on 12 Nov 2026". */
  note?: ReactNode;
  reached?: boolean;
  testId?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5" data-testid={testId}>
      <div className="flex items-baseline justify-between gap-2 text-[13px]">
        <span className="min-w-0 truncate font-semibold text-ink">{name}</span>
        <span className="num shrink-0 text-ink-soft">{amount}</span>
      </div>
      <ProgressBar pct={pct} reached={reached} label={typeof name === 'string' ? `${name} progress` : 'Goal progress'} />
      <div className="flex items-center justify-between gap-2 text-label">
        <span className={`inline-flex min-w-0 items-center gap-1.5 ${reached ? 'text-gold-ink' : 'text-ink-soft'}`}>
          {reached && <StatusIcon kind="reached" size={13} />}
          <span className="truncate">{note ?? (reached ? 'Goal reached' : '')}</span>
        </span>
        <span className="num shrink-0 text-ink-soft">{pctLabel}</span>
      </div>
    </div>
  );
}
