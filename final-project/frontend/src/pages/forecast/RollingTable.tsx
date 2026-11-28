import { Flag } from 'lucide-react';
import { StatusIcon } from '../../components/ui/StatusBadge';
import { fmtExpense, fmtMoney, fmtSigned } from '../../lib/format';
import type { ForecastRangeMonth, RollingForecast } from '../../lib/types';

/** "1.200–3.400 €": the 80 % range of one month, from the backend (formatting only). */
const between = (m: ForecastRangeMonth | undefined) =>
  m ? `${fmtMoney(m.low80, { round: true }).replace(/\s*€$/u, '')}–${fmtMoney(m.high80, { round: true })}` : '—';

/** A balance; below zero it is red AND says so (never colour alone). */
function Balance({ value, strong = false }: { value: number; strong?: boolean }) {
  if (value >= 0) return <span className={strong ? 'font-semibold' : ''} title={fmtMoney(value)}>{fmtMoney(value, R)}</span>;
  return (
    <span className={`inline-flex items-center gap-1 text-negative ${strong ? 'font-semibold' : ''}`} title={`Below zero: ${fmtMoney(value)}`}>
      <StatusIcon kind="negative" size={13} />
      <span className="sr-only">Below zero: </span>
      {fmtMoney(value, R)}
    </span>
  );
}

/** Whole euros: a 12-month forecast is an estimate, and every column has to fit next to the goals. */
const R = { round: true } as const;

/**
 * The rolling forecast month by month (the "Month by month" card).
 * Figures are the first line's; a balance column for every line. Free to use per
 * month is on the chart (dotted line, hover card) and the tile. "8 in 10 between"
 * is the 80 % range the backend sends (`ranges.months`, matched by month key).
 */
export function RollingTable({ data }: { data: RollingForecast }) {
  const first = data.lines[0];
  if (!first) return null;
  const many = data.lines.length > 1;
  const goals = !!data.include_goals;
  const anyGoalBought = goals && data.rows.some((r) => r.goals && r.goals.length > 0);
  const ranges = new Map((data.ranges?.months ?? []).map((m) => [m.key, m]));
  const showRange = ranges.size > 0;

  return (
    <div className="overflow-x-auto">
      <table className="data-table [&_td]:px-2 [&_th]:px-2 [&_td:first-child]:pl-5 [&_td:last-child]:pr-5 [&_th:first-child]:pl-5 [&_th:last-child]:pr-5">
        <thead>
          <tr>
            <th>Month</th>
            <th className="text-right">Cash in</th>
            <th className="text-right">Costs</th>
            <th className="text-right">Investments</th>
            <th className="text-right">Kept</th>
            {data.lines.map((l) => (
              <th key={l.key} className="text-right" title={`Balance at month end · ${l.name}`}>{many ? l.name : 'Balance'}</th>
            ))}
            {showRange && <th className="text-right">8 in 10 between</th>}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => {
            const v = r.values[first.key];
            const tag = r.actual ? 'recorded' : r.budget_from !== null && r.budget_from !== r.year ? `budget of ${r.budget_from}` : null;
            return (
              <tr key={r.key} className={r.actual ? 'text-ink-soft' : ''}>
                <td className={tag || r.goals?.length ? 'py-1.5' : ''}>
                  <span className="block font-medium">{r.month_name}</span>
                  {tag && <span className="block text-label text-ink-muted">{tag}</span>}
                  {goals && r.goals && r.goals.length > 0 && (
                    <span className="mt-0.5 flex flex-wrap gap-1" data-testid={`goals-bought-${r.key}`}>
                      {r.goals.map((g) => (
                        <span key={g.goal_id} className="chip num" title={`Goal bought: ${g.name} (the money leaves the account)`}>
                          <Flag size={11} aria-hidden className="text-positive" /><span className="sr-only">Goal bought:</span> {g.name} {fmtExpense(g.amount, R)}
                        </span>
                      ))}
                    </span>
                  )}
                </td>
                <td className="cell-num" title={fmtMoney(v.income)}>{fmtMoney(v.income, R)}</td>
                <td className="cell-num" title={fmtExpense(v.expenses)}>{fmtExpense(v.expenses, R)}</td>
                <td className="cell-num text-invest">{v.invested ? fmtExpense(v.invested, R) : '—'}</td>
                <td className={`cell-num ${v.savings > 0 ? 'text-positive' : ''}`} title={fmtSigned(v.savings)}>{fmtSigned(v.savings, R)}</td>
                {data.lines.map((l) => (
                  <td key={l.key} className="cell-num"><Balance value={r.values[l.key].balance} strong /></td>
                ))}
                {showRange && <td className="cell-num text-ink-soft">{r.actual ? '—' : between(ranges.get(r.key))}</td>}
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <td className="pl-5">
              Next 12 months
              {anyGoalBought && first.spent_on_goals ? <span className="block text-label font-normal text-ink-soft">goals bought {fmtExpense(first.spent_on_goals, R)}</span> : null}
            </td>
            <td />
            <td />
            <td />
            <td className={`cell-num ${first.kept > 0 ? 'text-positive' : ''}`} title={fmtSigned(first.kept)}>{fmtSigned(first.kept, R)}</td>
            {data.lines.map((l) => <td key={l.key} className="cell-num"><Balance value={l.end_balance} strong /></td>)}
            {showRange && <td className="pr-5" />}
          </tr>
        </tfoot>
      </table>
      {many && <p className="px-5 pt-2 text-label text-ink-muted">Cash in, costs and kept are for “{first.name}”.</p>}
    </div>
  );
}
