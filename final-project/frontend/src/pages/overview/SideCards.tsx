import { Card, EmptyState } from '../../components/ui/Card';
import { GoalProgress } from '../../components/ui/ProgressBar';
import { StatusText, type StatusKind } from '../../components/ui/StatusBadge';
import { fmtDate, fmtExpense, fmtMoney, fmtPct } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { Dashboard, GoalBrief, GoalState, UpcomingItem } from '../../lib/types';

/** Bills due within this many days are listed (the backend sends the next 30). */
const BILL_DAYS = 14;

const GOAL_KIND: Record<GoalState, StatusKind> = {
  on_track: 'positive', behind: 'warning', met: 'reached', overdue: 'negative', completed: 'neutral', abandoned: 'neutral',
};

/** The line under a goal bar: status word (+ icon) and one data point from the backend. */
function goalNote(g: GoalBrief, monthName: string) {
  if (g.status === 'met') return undefined; // GoalProgress shows ★ Goal reached
  const added = g.added_this_month > 0 ? ` · +${fmtMoney(g.added_this_month, { round: true })} in ${monthName}` : '';
  const text = g.status === 'behind' && g.required_monthly_pace !== null
    ? `Behind · needs ${fmtMoney(g.required_monthly_pace, { round: true })} a month`
    : g.status === 'overdue'
      ? `Overdue since ${fmtDate(g.target_date)}`
      : g.status === 'on_track'
        ? `On track · by ${fmtDate(g.target_date)}`
        : `By ${fmtDate(g.target_date)}`;
  return <StatusText kind={GOAL_KIND[g.status]}>{text}{added}</StatusText>;
}

export function SavingsGoalsCard({ data }: { data: Dashboard }) {
  const setTab = useUi((s) => s.setTab);
  const goals = data.goals.goals;
  return (
    <Card title="Savings goals" testId="overview-goals"
      meta={goals.length > 0 ? `${fmtMoney(data.kpis.earmarked, { round: true })} saved` : undefined}
      link={goals.length > 0 ? { label: 'Manage goals', onClick: () => setTab('forecast') } : undefined}>
      {goals.length === 0 ? (
        <EmptyState title="No goals yet"
          action={<button type="button" className="btn-secondary btn-sm" onClick={() => setTab('forecast')}>Add a goal</button>} />
      ) : (
        <div className="flex flex-col gap-4">
          {goals.map((g) => (
            <GoalProgress
              key={g.id}
              name={g.name}
              amount={`${fmtMoney(g.saved, { round: true })} of ${fmtMoney(g.target_amount, { round: true })}`}
              pct={g.progress_pct}
              pctLabel={fmtPct(g.progress_pct)}
              reached={g.status === 'met'}
              note={goalNote(g, data.month_name)}
            />
          ))}
        </div>
      )}
    </Card>
  );
}

function billStatus(b: UpcomingItem) {
  if (b.overdue) return <StatusText kind="negative">Overdue</StatusText>;
  if (!b.ready) return <StatusText kind="warning">{fmtMoney(b.short_by, { round: true })} short</StatusText>;
  if (b.source === 'fund' && b.goal_name) return <span className="text-label text-ink-soft">from “{b.goal_name}”</span>;
  return null;
}

export function UpcomingBillsCard({ data }: { data: Dashboard }) {
  const setTab = useUi((s) => s.setTab);
  // Overdue bills (days_left < 0) stay on the list; filtering only, no maths.
  const items = data.upcoming.items.filter((b) => b.days_left <= BILL_DAYS);
  const allReady = items.every((b) => b.ready && !b.overdue);
  return (
    <Card title="Upcoming bills" meta={`next ${BILL_DAYS} days`} testId="upcoming-bills"
      footer={items.length > 0 && (allReady
        ? <StatusText kind="positive">Covered by balance</StatusText>
        : <StatusText kind="warning">Not all covered yet</StatusText>)}
      link={{ label: 'Calendar', onClick: () => setTab('calendar') }}>
      {items.length === 0 ? (
        <p className="py-2 text-body text-ink-soft">No bills due in the next {BILL_DAYS} days.</p>
      ) : (
        <ul className="divide-y divide-line">
          {items.map((b) => (
            <li key={`${b.bill_id}-${b.due}`} className="grid grid-cols-[48px_minmax(0,1fr)_auto] items-center gap-x-3 py-2">
              <span className="num text-label text-ink-soft">{fmtDate(b.due, { short: true })}</span>
              <span className="min-w-0">
                <span className="block truncate text-[13px] text-ink">{b.name}</span>
                {billStatus(b)}
              </span>
              <span className="num text-[13px] text-ink">{fmtExpense(b.amount)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function InvestedCard({ data }: { data: Dashboard }) {
  const setTab = useUi((s) => s.setTab);
  const inv = data.investments;
  const plans = inv.plans.filter((p) => p.invested_month > 0);
  const nothing = data.kpis.invested === 0 && plans.length === 0;
  return (
    <Card title="Invested this month" testId="invested-month"
      link={{ label: 'Net worth', onClick: () => setTab('networth') }}>
      {nothing ? (
        <p className="py-1 text-body text-ink-soft">Nothing invested in {data.month_name}.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {plans.length > 0 ? plans.map((p) => (
            <li key={p.id} className="flex items-baseline justify-between gap-3 text-[13px]">
              <span className="min-w-0 truncate text-ink">{p.name}</span>
              <span className="num font-semibold text-invest">{fmtMoney(p.invested_month)}</span>
            </li>
          )) : (
            <li className="flex items-baseline justify-between gap-3 text-[13px]">
              <span className="text-ink">Investments</span>
              <span className="num font-semibold text-invest">{fmtMoney(data.kpis.invested)}</span>
            </li>
          )}
          {inv.invested_year > 0 && (
            <li className="num text-label text-ink-soft">{fmtMoney(inv.invested_year, { round: true })} invested in {data.year}</li>
          )}
        </ul>
      )}
    </Card>
  );
}
