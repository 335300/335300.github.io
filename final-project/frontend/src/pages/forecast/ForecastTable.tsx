import { fmtExpense, fmtMoney, fmtSigned } from '../../lib/format';
import type { Projection } from '../../lib/types';

export function ForecastTable({ data }: { data: Projection }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-line text-left text-xs text-ink-muted">
          <th className="py-2 font-medium">Month</th>
          <th className="py-2 font-medium">Source</th>
          <th className="py-2 text-right font-medium">Cash in</th>
          <th className="py-2 text-right font-medium">Costs</th>
          <th className="py-2 text-right font-medium">Invested</th>
          <th className="py-2 text-right font-medium">Kept</th>
          <th className="py-2 text-right font-medium">Balance</th>
        </tr>
      </thead>
      <tbody>
        {data.rows.map((r) => (
          <tr key={r.month} className={`border-b border-line/70 last:border-0 ${r.negative ? 'bg-negative-tint' : ''}`}>
            <td className="py-2 font-medium">{r.month_name}</td>
            <td className="py-2">
              {r.actual ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-primary-tint px-2 py-0.5 text-xs text-primary">● Recorded</span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full border border-dashed border-line px-2 py-0.5 text-xs text-ink-soft">○ From budget</span>
              )}
            </td>
            <td className="num py-2 text-right text-ink-soft">{r.income ? `+${fmtMoney(r.income)}` : fmtMoney(0)}</td>
            <td className="num py-2 text-right text-ink-soft">{fmtExpense(r.expenses)}</td>
            <td className="num py-2 text-right text-invest">{r.invested ? fmtExpense(r.invested) : '—'}</td>
            <td className={`num py-2 text-right ${r.savings < 0 ? 'text-negative' : r.savings > 0 ? 'text-positive' : ''}`}>{fmtSigned(r.savings)}</td>
            <td className={`num py-2 text-right font-semibold ${r.negative ? 'text-negative' : ''}`}>
              {r.negative && <span className="mr-1 text-xs font-medium">⚠ below zero</span>}
              {fmtMoney(r.balance)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
