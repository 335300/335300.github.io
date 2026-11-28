import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { CostsChart } from '../../components/charts/CostsChart';
import { Card, EmptyState } from '../../components/ui/Card';
import { fmtChange, fmtMoney } from '../../lib/format';
import type { CostStats, History } from '../../lib/types';

/**
 * Fixed and variable costs over the last twelve months, and how this month
 * compares with what is usual. Averages, median and changes are computed by the
 * backend (services/cashflow.py → history) from the months before this one.
 */
export function CostTrends({ data, monthName, hasUsual }: { data: History; monthName: string; hasUsual: boolean }) {
  const n = data.variable.months;
  return (
    <Card title="Fixed and variable costs over time" collapseKey="overview-cost-trends" collapseLabel="Fixed and variable costs over time">
      {data.rows.length === 0 ? (
        <EmptyState title="No months recorded yet">Add transactions to see how your costs move.</EmptyState>
      ) : (
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-8"><CostsChart rows={data.rows} /></div>
          <div className="col-span-4 space-y-4">
            <StatBlock title="Fixed costs" swatch="bg-primary" stats={data.fixed} monthName={monthName} hasUsual={hasUsual}
              rows={[{ label: n ? `Usual month (middle of the ${n} before)` : 'Usual month', value: data.fixed.median_6m }]} />
            <StatBlock title="Variable costs" swatch="bg-secondary" stats={data.variable} monthName={monthName} hasUsual={hasUsual}
              rows={[
                { label: '3-month average', value: data.variable.avg_3m },
                { label: `${n || 6}-month average`, value: data.variable.avg_6m },
                { label: 'Typical month (median)', value: data.variable.median_6m },
              ]}
              trend={data.variable.trend_pct} />
          </div>
        </div>
      )}
    </Card>
  );
}

function StatBlock({ title, swatch, stats, monthName, rows, trend, hasUsual }: {
  /** false = no earlier month holds data (backend costs.usual_months_with_data = 0): no usual figures. */
  hasUsual: boolean;
  title: string;
  swatch: string;
  stats: CostStats;
  monthName: string;
  rows: { label: string; value: number | null }[];
  trend?: number | null;
}) {
  return (
    <div className="rounded-lg border border-line px-3.5 py-3">
      <div className="flex items-center gap-2 text-xs font-medium text-ink-soft">
        <span className={`h-2.5 w-2.5 rounded-sm ${swatch}`} aria-hidden />
        {title} · {monthName}
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="num text-xl font-semibold">{fmtMoney(stats.current)}</span>
        {hasUsual && stats.vs_usual_pct !== null && <Change pct={stats.vs_usual_pct} suffix="vs usual" />}
      </div>
      {stats.one_off > 0 && <p className="num text-xs text-warning">{fmtMoney(stats.one_off)} of it one-off — not compared</p>}
      {hasUsual && <dl className="num mt-2 space-y-1 text-xs">
        {rows.map((r) => (
          <div key={r.label} className="flex justify-between gap-3">
            <dt className="text-ink-muted">{r.label}</dt>
            <dd className="font-medium text-ink">{r.value === null ? '—' : fmtMoney(r.value)}</dd>
          </div>
        ))}
        {trend !== undefined && trend !== null && (
          <div className="flex justify-between gap-3 border-t border-line/70 pt-1">
            <dt className="text-ink-muted">Last 3 months vs the 3 before</dt>
            <dd><Change pct={trend} /></dd>
          </div>
        )}
      </dl>}
      {(stats.months === 0 || !hasUsual) && <p className="mt-2 text-xs text-ink-muted">No earlier months to compare with yet.</p>}
    </div>
  );
}

/** A change with an arrow and a sign — rising costs are a heads-up, falling ones are good news. */
export function Change({ pct, suffix }: { pct: number; suffix?: string }) {
  const flat = Math.abs(pct) < 5;
  const tone = flat ? 'text-ink-muted' : pct > 0 ? 'text-warning' : 'text-secondary';
  const icon = flat ? <Minus size={12} /> : pct > 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />;
  return (
    <span className={`num inline-flex items-center gap-0.5 whitespace-nowrap text-xs font-medium ${tone}`}>
      {icon}
      {fmtChange(pct)}
      {suffix && <span className="font-normal">&nbsp;{suffix}</span>}
    </span>
  );
}
