import { AlertTriangle } from 'lucide-react';
import { useState } from 'react';
import { fmtMoney, fmtPct, MONTHS_SHORT } from '../../lib/format';
import type { Budgets, JobKey, PlannedSplit } from '../../lib/types';

/** Same colours as the Overview's "Where your income went". */
export const JOB_COLOUR: Record<JobKey, string> = {
  fixed: 'bg-primary',
  variable: 'bg-secondary',
  investment: 'bg-invest',
  savings: 'bg-positive',
};

/** "25%", "12,5%" — a backend share, shown with one decimal only when it has one. */
export function fmtShare(v: number): string {
  return fmtPct(v, Number.isInteger(v) ? 0 : 1);
}

/**
 * How the budget plan splits planned income: fixed costs, variable costs,
 * investment and savings, for the whole year or one month, against the same
 * planning guide the Overview uses. Every figure comes from the backend.
 */
export function AllocationPanel({ allocation, lastActual }: { allocation: Budgets['allocation']; lastActual: number | null }) {
  const [month, setMonth] = useState<number | null>(null);
  const split: PlannedSplit = month === null ? allocation.year : allocation.months[month];
  const period = month === null ? 'the year' : allocation.months[month].name;

  return (
    <section className="rounded-card border border-line p-4" aria-label="Planned split of income" data-testid="allocation-panel">
      <h3 className="text-card-title">Planned split of income</h3>

      {/* One small bar per month: the whole plan at a glance. Click one to see it below. */}
      <div className="mt-3 grid grid-cols-[auto_repeat(12,minmax(0,1fr))] items-end gap-1.5" role="radiogroup" aria-label="Show the split for">
        <MonthButton label="Year" selected={month === null} onClick={() => setMonth(null)} split={allocation.year} />
        {allocation.months.map((m) => (
          <MonthButton key={m.month} label={MONTHS_SHORT[m.month]} selected={month === m.month} onClick={() => setMonth(m.month)}
            split={m} muted={lastActual !== null && m.month <= lastActual} />
        ))}
      </div>

      {split.income === 0 && split.cash_out === 0 ? (
        <p className="mt-4 text-sm text-ink-muted">Nothing planned for {period} yet. Fill in the income and cost rows below.</p>
      ) : (
        <>
          <div className="mt-4 flex h-5 w-full overflow-hidden rounded-md bg-bg" role="img"
            aria-label={split.blocks.map((b) => `${b.label} ${fmtShare(b.share)}`).join(', ')}>
            {split.blocks.filter((b) => b.width > 0).map((b) => (
              <div key={b.key} className={`${JOB_COLOUR[b.key]} h-full border-r border-surface last:border-0`} style={{ width: `${b.width}%` }}
                title={`${b.label}: ${fmtMoney(b.amount)} · ${fmtShare(b.share)} of planned income`} />
            ))}
          </div>

          <div className="mt-4 grid grid-cols-4 gap-4">
            {split.blocks.map((b) => (
              <div key={b.key} data-testid={`allocation-${b.key}`}>
                <div className="flex items-center gap-1.5 text-xs font-medium text-ink-soft">
                  <span className={`h-2.5 w-2.5 rounded-sm ${JOB_COLOUR[b.key]}`} aria-hidden />
                  {b.label}
                </div>
                <div className={`num mt-0.5 text-lg font-semibold ${b.amount < 0 ? 'text-negative' : ''}`}>
                  {split.income ? fmtShare(b.share) : '–'}
                </div>
                <div className="num text-xs text-ink-muted">{fmtMoney(b.amount, { round: true })}{month === null ? ' in the year' : ''}</div>
              </div>
            ))}
          </div>

          {split.income === 0 ? (
            <Note>No income is planned for {period}, so there is nothing to take a share of. Add it in the income rows below.</Note>
          ) : split.shortfall > 0 ? (
            <Note>
              The plan spends <strong className="num">{fmtMoney(split.shortfall, { round: true })}</strong> more than it earns in {period} —
              that would come from the balance you already have.
            </Note>
          ) : null}
        </>
      )}
    </section>
  );
}

function MonthButton({ label, selected, onClick, split, muted }: {
  label: string;
  selected: boolean;
  onClick: () => void;
  split: PlannedSplit;
  muted?: boolean;
}) {
  const parts = split.blocks.filter((b) => b.width > 0);
  const summary = split.income
    ? split.blocks.map((b) => `${b.label} ${fmtShare(b.share)}`).join(', ')
    : 'no income planned';
  const warnings = [
    split.attention ? `${split.attention} outside the guide` : null,
    split.shortfall > 0 ? `spends ${fmtMoney(split.shortfall, { round: true })} more than it earns` : null,
  ].filter(Boolean).join(' · ');
  return (
    <button type="button" role="radio" aria-checked={selected} onClick={onClick}
      title={`${label}: ${summary}${warnings ? ` · ${warnings}` : ''}`}
      className={`flex min-w-[2.5rem] flex-col items-center gap-1 rounded-md px-1 pb-1 pt-1.5 text-xs ${
        selected ? 'bg-primary-tint text-primary ring-1 ring-primary/40' : 'text-ink-muted hover:bg-bg'
      } ${muted && !selected ? 'opacity-60' : ''}`}>
      <span className="flex h-12 w-4 flex-col-reverse overflow-hidden rounded-sm bg-bg" aria-hidden>
        {parts.map((b) => (
          <span key={b.key} className={JOB_COLOUR[b.key]} style={{ height: `${b.width}%` }} />
        ))}
      </span>
      <span className="flex items-center gap-0.5 font-medium">
        {label}
        {warnings && <AlertTriangle size={10} className="text-warning" aria-label={warnings} />}
      </span>
    </button>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 flex items-start gap-2 rounded-lg bg-warning-tint px-3 py-2.5 text-[13px] text-warning-ink">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <p>{children}</p>
    </div>
  );
}
