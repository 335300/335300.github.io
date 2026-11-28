import { Plus } from 'lucide-react';
import { useState } from 'react';
import { ForecastChart, type ForecastPoint } from '../charts/ForecastChart';
import { applyAppearance } from '../../lib/appearance';
import { fmtMoney } from '../../lib/format';
import { BudgetBarLegend, BudgetBarRow } from './BudgetBarRow';
import { Card } from './Card';
import { ConfirmButton } from './ConfirmButton';
import { Field } from './Field';
import { KpiTile } from './KpiTile';
import { GoalProgress } from './ProgressBar';
import { EmptyState, ErrorState, Skeleton } from './States';
import { BudgetBadge, GoalBadge, StatusBadge } from './StatusBadge';
import { showUndo } from './UndoToast';

/**
 * Developer view of every shared part, opened with #ui-gallery. Fixed, made-up
 * round numbers only (no data is read). Used for UI checks in light and dark.
 */
const POINTS: ForecastPoint[] = [
  { label: 'Jun', actual: 3000 }, { label: 'Jul', actual: 3100 }, { label: 'Aug', actual: 2700 },
  { label: 'Sep', actual: 3000 }, { label: 'Oct', actual: 3400 }, { label: 'Nov', actual: 3300, band50: [3300, 3300], band80: [3300, 3300] },
  { label: 'Dec', likely: 3100, band50: [2850, 3350], band80: [2600, 3600] },
  { label: 'Jan', likely: 3300, band50: [2900, 3700], band80: [2500, 4100] },
  { label: 'Feb', likely: 3500, band50: [3000, 4000], band80: [2500, 4500] },
  { label: 'Mar', likely: 3700, band50: [3050, 4350], band80: [2400, 5000] },
  { label: 'Apr', likely: 3800, band50: [3000, 4600], band80: [2300, 5300] },
  { label: 'May', likely: 4000, band50: [3100, 4900], band80: [2200, 5800] },
];

export function Gallery() {
  const [rowSel, setRowSel] = useState(2);
  return (
    <div className="flex flex-col gap-6" data-testid="ui-gallery">
      <div className="flex items-center justify-between">
        <h1 className="text-page-title">Shared parts</h1>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => applyAppearance('light')}>Light</button>
          <button className="btn-secondary" onClick={() => applyAppearance('dark')}>Dark</button>
          <button className="btn-secondary" onClick={() => applyAppearance('system')}>Match Mac</button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <KpiTile variant="hero" label="Kept this month" value={fmtMoney(600, { round: true, sign: true })} tone="positive"
          comparison={{ direction: 'up', tone: 'good', text: `${fmtMoney(100, { round: true })} more than your usual month` }}
          help="Cash in minus cash out this month." onHelpMore={() => undefined} />
        <KpiTile variant="hero" label="Liquidity" value={fmtMoney(8000, { round: true })}
          comparison={{ direction: 'none', text: 'Covers about 3 months of spending' }} help="Balance minus money saved for goals." />
        <KpiTile variant="hero" label="Wealth built" value={fmtMoney(1000, { round: true, sign: true })} tone="positive"
          comparison={{ direction: 'down', tone: 'bad', text: `${fmtMoney(200, { round: true })} less than your usual month` }} />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <KpiTile variant="compact" label="Balance" value={fmtMoney(3000, { round: true })} comparison={{ direction: 'up', text: `${fmtMoney(100, { round: true })} above usual` }} />
        <KpiTile variant="compact" label="Cash in" value={fmtMoney(4000, { round: true })} comparison={{ direction: 'same', text: 'About the same as usual' }} />
        <KpiTile variant="compact" label="Cash out" value={fmtMoney(-3500, { round: true })} comparison={{ direction: 'down', text: `${fmtMoney(100, { round: true })} less than usual` }} />
      </div>

      <div className="grid grid-cols-2 items-start gap-4">
        <Card title="Upcoming bills" help="Bills due in the next 14 days." meta="next 14 days"
          footer={`Total ${fmtMoney(-1300)}`} link={{ label: 'Open calendar →', onClick: () => undefined }} collapseKey="gallery-bills" collapseLabel="Upcoming bills">
          <table className="data-table">
            <tbody>
              {[['21 Nov', 'Rent', -1100], ['24 Nov', 'Phone', -100], ['28 Nov', 'Insurance', -100]].map(([d, n, a]) => (
                <tr key={String(n)}><td className="w-16 text-ink-soft">{d}</td><td>{n}</td><td className="cell-num">{fmtMoney(Number(a))}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card title="Status badges and goals">
          <div className="flex flex-wrap gap-2">
            <StatusBadge kind="positive">On track</StatusBadge>
            <StatusBadge kind="warning">Close to limit</StatusBadge>
            <StatusBadge kind="negative">Over budget</StatusBadge>
            <StatusBadge kind="info">Imported</StatusBadge>
            <StatusBadge kind="neutral">No budget</StatusBadge>
            <BudgetBadge status="warning" />
            <GoalBadge status="met" />
          </div>
          <div className="mt-4 flex flex-col gap-4">
            <GoalProgress name="Emergency fund" amount={`${fmtMoney(6000, { round: true })} of ${fmtMoney(9000, { round: true })}`} pct={67} pctLabel="67%" note="About 9 months to go" />
            <GoalProgress name="New bike" amount={`${fmtMoney(1000, { round: true })} of ${fmtMoney(1000, { round: true })}`} pct={100} pctLabel="100%" reached note="Goal reached on 12 Nov 2026" />
          </div>
        </Card>
      </div>

      <Card title="Budget vs real" meta={<BudgetBarLegend />}>
        <BudgetBarRow label="Groceries" usedPct={70} usualPct={90} status="under" amount={`${fmtMoney(300, { round: true })} of ${fmtMoney(400, { round: true })}`} statusText={`On track · ${fmtMoney(100, { round: true })} left`} />
        <BudgetBarRow label="Dining out" usedPct={85} usualPct={80} status="warning" amount={`${fmtMoney(120, { round: true })} of ${fmtMoney(140, { round: true })}`} statusText={`Close to limit · ${fmtMoney(20, { round: true })} left`} />
        <BudgetBarRow label="Clothing" usedPct={130} usualPct={70} status="over" amount={`${fmtMoney(130, { round: true })} of ${fmtMoney(100, { round: true })}`} statusText={`Over by ${fmtMoney(30, { round: true })}`} />
        <BudgetBarRow label="Gifts" usedPct={null} status="unbudgeted" noBudgetPct={30} amount={`${fmtMoney(40, { round: true })} spent`} statusText="No budget set" />
      </Card>

      <div className="rounded-card border border-line bg-surface shadow-card">
        <div className="max-h-[260px] overflow-auto rounded-card">
          <table className="data-table">
            <thead><tr><th>Date</th><th>Payee</th><th>Category</th><th className="text-right">Amount</th></tr></thead>
            <tbody>
              {[['19 Nov', 'Market', 'Groceries', -60], ['18 Nov', 'Salary', 'Income', 3000], ['18 Nov', 'Power', 'Utilities', -80], ['17 Nov', 'Shop', 'Household', -30]].map(([d, p, c, a], i) => (
                <tr key={i} tabIndex={0} aria-selected={rowSel === i} onClick={() => setRowSel(i)}>
                  <td className="text-ink-soft">{d}</td><td>{p}</td>
                  <td><span className="chip"><span className="h-2 w-2 rounded-full bg-chart-2" aria-hidden />{c}</span></td>
                  <td className={`cell-num ${Number(a) > 0 ? 'text-positive' : ''}`}>{fmtMoney(Number(a), { sign: true })}</td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr><td colSpan={3}>4 transactions · 1 selected</td><td className="cell-num">{fmtMoney(2830, { sign: true })}</td></tr></tfoot>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-2 items-start gap-4">
        <Card title="Inputs and buttons">
          <div className="grid grid-cols-2 gap-4">
            <Field id="g-payee" label="Payee"><input id="g-payee" className="input" defaultValue="Market" /></Field>
            <Field id="g-date" label="Date" hint="Today"><input id="g-date" className="input num" defaultValue="19.11.2026" /></Field>
            <Field id="g-amount" label="Amount" error="Use a comma for cents, e.g. 64,18">
              <input id="g-amount" className="input input-error num" defaultValue="64.18,0" aria-describedby="g-amount-error" />
            </Field>
            <Field id="g-acc" label="Account"><input id="g-acc" className="input" disabled defaultValue="Main account (locked)" /></Field>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button className="btn-primary">Save transaction</button>
            <button className="btn-secondary">Import CSV</button>
            <button className="btn-ghost">Cancel</button>
            <button className="btn-primary" disabled>Disabled</button>
            <button className="btn-secondary btn-sm">Compact 24px</button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <ConfirmButton label="Delete 3 transactions…" question="Delete 3 transactions? You can undo for 10 seconds."
              onConfirm={() => showUndo('3 transactions deleted.', () => undefined)} />
          </div>
        </Card>
        <Card title="Forecast · next 6 months">
          <ForecastChart points={POINTS} />
        </Card>
      </div>

      <div className="grid grid-cols-3 items-start gap-4">
        <Card>
          <EmptyState title="No transactions in December yet" icon={<Plus size={16} />}
            action={<><button className="btn-primary">Add transaction</button><button className="btn-secondary">Import CSV</button></>}>
            Add one by hand or import your bank’s CSV.
          </EmptyState>
        </Card>
        <Card><Skeleton /></Card>
        <Card>
          <ErrorState title="The forecast couldn’t be updated" onRetry={() => undefined}>
            No data was lost — all your entries are saved.
          </ErrorState>
        </Card>
      </div>
    </div>
  );
}
