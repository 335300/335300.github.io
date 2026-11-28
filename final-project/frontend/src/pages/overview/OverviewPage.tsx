import { Plus, Upload } from 'lucide-react';
import { useState } from 'react';
import { useAttention, useDashboard, useProfiles, useYears } from '../../api/queries';
import { CashFlowChart } from '../../components/charts/CashFlowChart';
import { Donut } from '../../components/charts/Donut';
import { InvestmentCard } from '../../components/investments/InvestmentCard';
import { Card, EmptyState } from '../../components/ui/Card';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { ProgressBar } from '../../components/ui/ProgressBar';
import { requestAddTransaction, shortcutLabel } from '../../components/ui/shortcuts';
import { fmtExpense, fmtMoney, fmtPct } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { Dashboard } from '../../lib/types';
import { ImportModal } from '../transactions/ImportModal';
import { AttentionBanner } from './AttentionBanner';
import { BillsGoalsCalendar } from './BillsGoalsCalendar';
import { BudgetCard } from './BudgetCard';
import { Change, CostTrends } from './CostTrends';
import { DistributionCard } from './DistributionCard';
import { EmergencyFundTile } from './EmergencyFundTile';
import { ForecastCard } from './ForecastCard';
import { JointOverview } from './JointOverview';
import { OverviewKpis } from './OverviewKpis';
import { PositionCard } from './PositionCard';
import { RecentTransactions } from './RecentTransactions';
import { InvestedCard, SavingsGoalsCard, UpcomingBillsCard } from './SideCards';

export function OverviewPage({ year }: { year: number }) {
  const isJoint = useProfiles().data?.active === 'joint';
  return isJoint ? <JointOverview year={year} /> : <PersonalOverview year={year} />;
}

/** ⌘N and the button do the same: the page on screen that has an add form opens it, else Transactions does. */
function addTransaction(setTab: (t: 'transactions') => void) {
  if (requestAddTransaction()) return;
  setTab('transactions');
  setTimeout(() => requestAddTransaction(), 50);
}

/**
 * Personal Overview (design C1/C2): what needs a look, the headline numbers,
 * budgets, the next six months, goals, bills and the latest transactions —
 * then every detail card below. All figures come from the backend.
 */
function PersonalOverview({ year }: { year: number }) {
  const month = useUi((s) => s.selectedMonth);
  const setTab = useUi((s) => s.setTab);
  const { data, error, isLoading } = useDashboard(year, month);
  const attention = useAttention(year, month).data;
  const today = useYears().data?.today ?? new Date().toISOString().slice(0, 10);
  const [importOpen, setImportOpen] = useState(false);

  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error} />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-page-title text-ink">Overview</h1>
          <span className="num text-[13px] text-ink-soft">
            {data.month_name} {data.year}
            {attention && ` · day ${attention.day} of ${attention.days_in_month}`}
          </span>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn-secondary" onClick={() => setImportOpen(true)}>
            <Upload size={14} aria-hidden /> Import CSV
          </button>
          <button type="button" className="btn-primary" onClick={() => addTransaction(setTab)}>
            <Plus size={14} aria-hidden /> Add transaction
            <span className="ml-1 text-label opacity-80">{shortcutLabel('N')}</span>
          </button>
        </div>
      </div>

      <AttentionBanner year={year} month={data.month} rows={data.budget_vs_real.rows} />
      <OverviewKpis data={data} />

      <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)] items-start gap-5">
        <div className="flex min-w-0 flex-col gap-5">
          <BudgetCard data={data} />
          <ForecastCard />
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <SavingsGoalsCard data={data} />
          <UpcomingBillsCard data={data} />
          <InvestedCard data={data} />
        </div>
      </div>

      <RecentTransactions year={year} month={data.month} monthName={data.month_name} />

      <h2 className="pt-2 text-label font-semibold uppercase tracking-wide text-ink-soft">More detail</h2>
      <div className="grid grid-cols-12 items-start gap-5">
        <DistributionCard className="col-span-6" data={data.distribution} year={year} />
        <Investments data={data} year={year} today={today} />
      </div>
      <div className="grid grid-cols-12 items-start gap-5">
        <div className="col-span-8"><PositionCard data={data.position} /></div>
        <EmergencyFundTile className="col-span-4" data={data.emergency} />
      </div>
      <SpendingSplit data={data} />
      <CostTrends data={data.history} monthName={data.month_name} hasUsual={data.costs.usual_months_with_data > 0} />
      <Card title="Cash in vs cash out" collapseKey="overview-cashflow" collapseLabel="Cash in vs cash out">
        {data.history.rows.length ? (
          <CashFlowChart rows={data.history.rows} />
        ) : (
          <EmptyState title="No months recorded yet">Add transactions to see the trend.</EmptyState>
        )}
      </Card>
      <BillsGoalsCalendar key={`${data.year}-${data.month}`} data={data} />
      <ImportModal year={year} open={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  );
}

function SpendingSplit({ data }: { data: Dashboard }) {
  const c = data.costs;
  const hasUsual = c.usual_months_with_data > 0;
  return (
    <Card title="Where the money went" collapseKey="overview-spending" collapseLabel="Where the money went">
      {c.month_spend === 0 ? (
        <EmptyState title="No spending recorded this month" />
      ) : (
        <div className="grid grid-cols-2 gap-8">
          <div>
          <div className="flex items-center gap-6">
            <Donut fixed={c.fixed} variable={c.variable} total={c.month_spend} />
            <div className="flex-1 space-y-3">
              <Legend swatch="bg-primary" label="Fixed costs" amount={c.fixed.total} share={c.fixed.share} />
              <Legend swatch="bg-secondary" label="Variable costs" amount={c.variable.total} share={c.variable.share} />
            </div>
          </div>
          {c.unusual.length > 0 && (
            <div className="mt-4 rounded-input bg-warning-tint px-3 py-2 text-xs text-warning-ink" role="status">
              <p className="font-medium">Unusual this month</p>
              <ul className="num mt-0.5">
                {c.unusual.map((u) => (
                  <li key={u.cat}>⚠ {u.cat} {fmtMoney(u.amount, { round: true })}, usual {fmtMoney(u.usual, { round: true })}</li>
                ))}
              </ul>
            </div>
          )}
          </div>
          <ul className="space-y-2.5">
            {c.ranked.map((r) => (
              <li key={r.cat} className="grid grid-cols-[1fr_auto_auto] items-center gap-x-3 gap-y-1">
                <span className="flex items-center gap-1.5 truncate text-sm">
                  <span className={`h-2 w-2 shrink-0 rounded-sm ${r.kind === 'fixed' ? 'bg-primary' : 'bg-secondary'}`} aria-hidden />
                  {r.cat}
                  <span className="text-xs text-ink-muted">· {r.kind}</span>
                  {r.one_off > 0 && <span className="num text-xs text-warning">· {fmtMoney(r.one_off, { round: true })} one-off</span>}
                </span>
                <span title={hasUsual && r.usual !== null ? `Usual month: ${fmtMoney(r.usual)}` : undefined}>
                  {!hasUsual ? null : r.vs_usual_pct !== null ? <Change pct={r.vs_usual_pct} /> : r.usual === 0 && <span className="text-xs text-ink-muted">new</span>}
                </span>
                <span className="num text-sm">{fmtExpense(r.amount)}</span>
                <div className="col-span-3">
                  <ProgressBar pct={r.width} tone={r.kind === 'fixed' ? 'primary' : 'secondary'} height="h-1.5" label={`${r.cat} share`} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function Legend({ swatch, label, amount, share }: { swatch: string; label: string; amount: number; share: number }) {
  return (
    <div>
      <div className="flex items-center gap-2 text-sm">
        <span className={`h-2.5 w-2.5 rounded-sm ${swatch}`} aria-hidden />
        <span className="font-medium">{label}</span>
        <span className="num ml-auto">{fmtMoney(amount)}</span>
      </div>
      <div className="num mt-0.5 text-right text-xs text-ink-muted">{fmtPct(share)}</div>
    </div>
  );
}

function Investments({ data, year, today }: { data: Dashboard; year: number; today: string }) {
  const inv = data.investments;
  const setTab = useUi((s) => s.setTab);
  return (
    <Card
      className="col-span-6"
      title="Investments"
      collapseKey="overview-investments"
      collapseLabel="Investments"
      subtitle={
        inv.invested_year
          ? `${fmtMoney(inv.invested_month)} invested in ${data.month_name} · ${fmtMoney(inv.invested_year)} in ${year}`
          : undefined
      }
    >
      {inv.plans.length ? (
        <div className="space-y-4">
          {inv.plans.map((p) => <InvestmentCard key={p.id} plan={p} year={year} month={data.month} today={today} />)}
        </div>
      ) : (
        <EmptyState title="No investment plan yet">
          Paying something off in instalments — land, a flat? <button className="font-medium text-primary underline-offset-2 hover:underline" onClick={() => setTab('forecast')}>Add it in the Forecast tab</button> to follow its progress here.
        </EmptyState>
      )}
    </Card>
  );
}
