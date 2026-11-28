import { useState } from 'react';
import { BudgetBarLegend, BudgetBarRow } from '../../components/ui/BudgetBarRow';
import { Card, EmptyState } from '../../components/ui/Card';
import { ProgressBar } from '../../components/ui/ProgressBar';
import { BudgetBadge, budgetBarTone } from '../../components/ui/StatusBadge';
import { fmtMoney, fmtPct } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { Dashboard } from '../../lib/types';

type Row = Dashboard['budget_vs_real']['rows'][number];

/** The words under a bar; amounts are the backend's `real`, `budget` and `diff` (budget − real). */
function statusText(r: Row): string {
  switch (r.status) {
    case 'over': return `Over by ${fmtMoney(-r.diff, { round: true })}`;
    case 'warning': return `Close to limit · ${fmtMoney(r.diff, { round: true })} left`;
    case 'on_budget': return 'On budget · nothing left';
    case 'unbudgeted': return 'No budget set';
    default: return `On track · ${fmtMoney(r.diff, { round: true })} left`;
  }
}

/**
 * Budget vs real (Overview): one bar per variable budget, with the usual month
 * as a │ marker, and a table view of every budget. Every amount, percentage and
 * status comes from services/dashboard.py.
 */
export function BudgetCard({ data }: { data: Dashboard }) {
  const b = data.budget_vs_real;
  const setTab = useUi((s) => s.setTab);
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const variable = b.rows.filter((r) => r.kind === 'variable');
  const vt = b.variable_totals;

  return (
    <Card
      title="Budget vs real"
      meta={view === 'chart' && variable.length > 0 && (
        <span className="inline-flex items-center gap-2">variable budgets{variable.some((r) => r.usual_pct !== null) && <> · <BudgetBarLegend /></>}</span>
      )}
      action={b.rows.length > 0 && (
        <div className="flex rounded-input border border-line text-label" role="radiogroup" aria-label="Show budget vs real as">
          {(['chart', 'table'] as const).map((v) => (
            <button key={v} type="button" role="radio" aria-checked={view === v} onClick={() => setView(v)}
              className={`px-2 py-0.5 ${view === v ? 'bg-primary-tint text-primary' : 'text-ink-soft'}`}>
              {v === 'chart' ? 'Chart' : 'Table'}
            </button>
          ))}
        </div>
      )}
      footer={view === 'chart' && variable.length > 0
        ? `${fmtMoney(vt.spent, { round: true })} of ${fmtMoney(vt.budget, { round: true })} spent${vt.days_left !== null ? ` · ${vt.days_left} day${vt.days_left === 1 ? '' : 's'} left` : ''}`
        : undefined}
      link={{ label: 'All budgets', onClick: () => setTab('forecast') }}
    >
      {b.rows.length === 0 ? (
        <EmptyState title="No budgets or spending this month">Set monthly budgets in the Forecast tab.</EmptyState>
      ) : view === 'chart' ? (
        variable.length === 0 ? (
          <EmptyState title="No variable budgets this month">Switch to Table to see every budget.</EmptyState>
        ) : (
          <div data-testid="budget-chart">
            {variable.map((r) => (
              <BudgetBarRow
                key={r.cat}
                testId={`budget-row-${r.cat}`}
                label={r.cat}
                usedPct={r.used_pct}
                usualPct={r.usual_pct}
                status={r.status}
                amount={r.status === 'unbudgeted'
                  ? `${fmtMoney(r.real, { round: true })} spent`
                  : `${fmtMoney(r.real, { round: true })} of ${fmtMoney(r.budget, { round: true })}`}
                statusText={statusText(r)}
              />
            ))}
          </div>
        )
      ) : (
        <BudgetTable data={data} />
      )}
    </Card>
  );
}

/** Every budget (fixed, variable, investments) as a table — the view the Overview always had. */
function BudgetTable({ data }: { data: Dashboard }) {
  const b = data.budget_vs_real;
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Category</th>
          <th className="text-right">Budget</th>
          <th className="text-right">Spent</th>
          <th className="w-[28%]">Used</th>
          <th className="text-right">Left</th>
        </tr>
      </thead>
      <tbody>
        {b.rows.map((r) => (
          <tr key={r.cat}>
            <td className="cell-wrap py-2">
              <div className="font-medium">{r.cat}</div>
              <div className="mt-1">
                <BudgetBadge status={r.status}
                  detail={r.status === 'warning' && r.used_pct !== null ? `${fmtPct(r.used_pct)} used` : undefined} />
              </div>
            </td>
            <td className="cell-num text-ink-soft">{r.budget ? fmtMoney(r.budget) : '—'}</td>
            <td className="cell-num">{fmtMoney(r.real)}</td>
            <td><ProgressBar pct={r.progress} tone={budgetBarTone(r.status)} label={`${r.cat} budget used`} /></td>
            <td className={`cell-num ${r.status === 'over' ? 'font-medium text-negative' : 'text-ink-soft'}`}>
              {r.budget ? (r.diff < 0 ? `${fmtMoney(-r.diff)} over` : fmtMoney(r.diff)) : '—'}
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td>Total</td>
          <td className="cell-num">{fmtMoney(b.total.budget)}</td>
          <td className="cell-num">{fmtMoney(b.total.real)}</td>
          <td />
          <td className={`cell-num ${b.total.status === 'over' ? 'text-negative' : ''}`}>
            {b.total.diff < 0 ? `${fmtMoney(-b.total.diff)} over` : fmtMoney(b.total.diff)}
          </td>
        </tr>
      </tfoot>
    </table>
  );
}
