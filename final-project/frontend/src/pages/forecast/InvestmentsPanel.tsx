import { Plus } from 'lucide-react';
import { useState } from 'react';
import { useInvestments, useYears } from '../../api/queries';
import { InvestmentCard } from '../../components/investments/InvestmentCard';
import { InvestmentForm } from '../../components/investments/InvestmentForm';
import { Card, EmptyState } from '../../components/ui/Card';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { fmtMoney } from '../../lib/format';

/**
 * Investment plans: create, edit and follow them. The Overview shows the same
 * cards for the month picked there; this tab has no month picker, so the cards
 * are seen from today — or from December when a past year is open.
 */
export function InvestmentsPanel({ year, today }: { year: number; today: string }) {
  const current = useYears().data;
  const month = current && current.current_year === year ? current.current_month : 11;
  const { data, isLoading, error } = useInvestments(year, month);
  const [creating, setCreating] = useState(false);

  return (
    <Card
      title="Investments"
      collapseKey="forecast-investments"
      collapseLabel="Investments"
      action={<button className="btn-primary btn-sm" onClick={() => setCreating(true)}><Plus size={14} /> New plan</button>}
    >
      {isLoading ? <Loading /> : error || !data ? <ErrorNote error={error} /> : data.plans.length ? (
        <>
          <div className="grid grid-cols-1 gap-4">
            {data.plans.map((p) => <InvestmentCard key={p.id} plan={p} year={year} month={month} today={today} manage />)}
          </div>
          {data.value_at_cost > 0 && (
            <p className="num mt-3 text-xs text-ink-muted">
              Built so far, at what it cost you: about <strong className="text-ink">{fmtMoney(data.value_at_cost, { round: true })}</strong> ·
              invested in {year}: <strong className="text-ink">{fmtMoney(data.invested_year)}</strong> recorded.
            </p>
          )}
        </>
      ) : (
        <EmptyState title="No investment plan yet">Paying off land, a flat or anything else in instalments? Add it to follow its progress.</EmptyState>
      )}
      {creating && <InvestmentForm open year={year} onClose={() => setCreating(false)} />}
    </Card>
  );
}
