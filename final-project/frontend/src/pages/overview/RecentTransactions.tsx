import { useCategories, useTransactions } from '../../api/queries';
import { Card, EmptyState } from '../../components/ui/Card';
import { categoryDotClass } from '../../components/ui/CategoryDot';
import { ErrorNote } from '../../components/ui/Feedback';
import { Skeleton } from '../../components/ui/States';
import { shortcutLabel } from '../../components/ui/shortcuts';
import { fmtDate, fmtExpense, fmtMoney } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { Transaction } from '../../lib/types';

/**
 * The latest transactions of the month (newest first). Sorting and cutting the
 * list is display only; amounts are shown as recorded.
 */
export function RecentTransactions({ year, month, monthName, joint = false, limit = 6 }: {
  year: number;
  month: number;
  monthName: string;
  /** Joint wording ("Latest from our shared account"). */
  joint?: boolean;
  limit?: number;
}) {
  const setTab = useUi((s) => s.setTab);
  const { data, error, isLoading } = useTransactions(year, { month });
  const cats = useCategories(year).data;
  const expense = cats?.expense ?? [];
  const kindOf = (t: Transaction) => expense.find((c) => c.name === t.cat)?.kind;
  const dotOf = (t: Transaction) => categoryDotClass(t.cat, kindOf(t), t.type === 'income');
  const rows = [...(data?.transactions ?? [])]
    .sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id)
    .slice(0, limit);

  return (
    <Card
      title={joint ? 'Latest from our shared account' : 'Recent transactions'}
      link={{ label: joint ? 'See everything' : `All transactions ${shortcutLabel('2')}`, onClick: () => setTab('transactions') }}
      testId="recent-transactions"
    >
      {isLoading ? (
        <Skeleton lines={4} />
      ) : error ? (
        <ErrorNote error={error} />
      ) : rows.length === 0 ? (
        <EmptyState title={joint ? `Nothing recorded in ${monthName} yet` : `No transactions in ${monthName} yet`} />
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th className="w-24">Date</th>
              <th>{joint ? 'What' : 'Payee'}</th>
              <th>Category</th>
              <th className="w-40 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => {
              const invest = t.type === 'expense' && kindOf(t) === 'investment';
              return (
                <tr key={t.id}>
                  <td className="num text-ink-soft">{fmtDate(t.date, { short: true })}</td>
                  <td className="max-w-0 truncate">{t.desc || t.payee || '—'}</td>
                  <td>
                    <span className={`chip ${invest ? 'bg-invest-tint text-invest' : ''}`}>
                      <span className={`h-2 w-2 rounded-pill ${dotOf(t)}`} aria-hidden />
                      {t.cat}
                    </span>
                  </td>
                  <td className={`cell-num ${t.type === 'income' ? 'text-positive' : ''}`}>
                    {t.type === 'income' ? fmtMoney(t.amount, { sign: true }) : fmtExpense(t.amount)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Card>
  );
}
