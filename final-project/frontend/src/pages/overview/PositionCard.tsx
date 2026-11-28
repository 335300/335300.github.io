import { AlertTriangle } from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { fmtMoney } from '../../lib/format';
import type { Position } from '../../lib/types';

const SWATCH: Record<Position['parts'][number]['key'], string> = {
  liquid: 'bg-primary',
  goals: 'bg-positive',
  investments: 'bg-invest',
};

/**
 * Liquidity at a glance: everything you own, by how freely you can use it.
 * Amounts, bar widths and the months of costs covered come from the backend
 * (services/cashflow.py → position, measured against costs_yardstick).
 */
export function PositionCard({ data }: { data: Position }) {
  return (
    <Card title="Where your money is">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-bg" role="img"
        aria-label={data.parts.map((p) => `${p.label} ${fmtMoney(p.amount)}`).join(', ')}>
        {data.parts.filter((p) => p.width > 0).map((p) => (
          <div key={p.key} className={`${SWATCH[p.key]} h-full border-r border-surface last:border-0`} style={{ width: `${p.width}%` }}
            title={`${p.label}: ${fmtMoney(p.amount)}`} />
        ))}
      </div>
      <div className="mt-3 grid grid-cols-4 gap-4">
        {data.parts.map((p) => (
          <div key={p.key}>
            <div className="flex items-center gap-1.5 text-xs font-medium text-ink-soft">
              <span className={`h-2.5 w-2.5 rounded-sm ${SWATCH[p.key]}`} aria-hidden />
              {p.key === 'liquid' ? 'Liquidity' : p.label}
            </div>
            <div className={`num mt-0.5 text-lg font-semibold ${p.key === 'liquid' ? (p.amount < 0 ? 'text-negative' : 'text-primary') : ''}`}>
              {p.key === 'investments' && p.amount > 0 ? '≈ ' : ''}{fmtMoney(p.amount, p.key === 'investments' ? { round: true } : {})}
            </div>
            {p.key === 'liquid' && (
              <div className="num mt-1 text-xs text-ink-muted">
                {data.runway_months !== null && data.usual_costs !== null
                  ? `≈ ${data.runway_months} month${data.runway_months === 1 ? '' : 's'} of costs at ${
                      data.costs_basis === 'this_month'
                        ? `this month's ${fmtMoney(data.usual_costs, { round: true })} (no earlier month to go by yet)`
                        : `a typical ${fmtMoney(data.usual_costs, { round: true })} a month`
                    }`
                  : 'Months of costs covered show up once costs are recorded'}
              </div>
            )}
          </div>
        ))}
        <div className="border-l border-line pl-4">
          <div className="text-xs font-medium text-ink-soft">All together</div>
          <div className="num mt-0.5 text-lg font-semibold">{data.invested_value > 0 ? '≈ ' : ''}{fmtMoney(data.total, { round: data.invested_value > 0 })}</div>
          <div className="text-xs text-ink-muted">Balance {fmtMoney(data.balance)} plus investments</div>
        </div>
      </div>
      {data.over_earmarked && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-warning-tint px-3 py-2.5 text-sm text-warning">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <p>
            Your goals hold <strong className="num">{fmtMoney(data.earmarked)}</strong>, more than the{' '}
            <strong className="num">{fmtMoney(data.balance)}</strong> in the account — part of that saving has already been spent.
          </p>
        </div>
      )}
    </Card>
  );
}
