import { AlertTriangle, Check, Eye, EyeOff, PiggyBank, Plus } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { useGoals, usePrefs, useUpdatePrefs } from '../../api/queries';
import { Card, EmptyState } from '../../components/ui/Card';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { fmtExpense, fmtMoney, fmtSigned } from '../../lib/format';
import type { Allocation } from '../../lib/types';
import { GoalCard } from './GoalCard';
import { GoalForm } from './GoalForm';

export function GoalsPanel({ year, today, shared = false, title = 'Savings goals', shareLine }: {
  year: number;
  today: string;
  /** Joint: goals we save for together — plain words, no "savings this year" tile. */
  shared?: boolean;
  title?: string;
  /** Joint: one extra line under a goal ("€100 a month gets us there — €50 from each of us"). */
  shareLine?: (goalId: number) => ReactNode;
}) {
  const { data, isLoading, error } = useGoals(year);
  const [creating, setCreating] = useState(false);
  const prefs = usePrefs();
  const updatePrefs = useUpdatePrefs();
  const showSavingsTile = prefs.data?.show_savings_tile ?? false;
  const toggleSavingsTile = () => updatePrefs.mutate({ show_savings_tile: !showSavingsTile });
  const s = data?.summary;

  return (
    <Card
      title={title}
      collapseKey="forecast-goals"
      collapseLabel={title}
      subtitle={shared
        ? 'Something we save for together, with a target and a date. Each of us pays in our part.'
        : undefined}
      action={
        <div className="flex items-center gap-1">
          {!shared && (
            <button className="btn-icon btn-sm h-7 w-7" onClick={toggleSavingsTile} aria-pressed={showSavingsTile}
              aria-label={showSavingsTile ? 'Hide savings' : 'Show savings'} title={showSavingsTile ? 'Hide savings not assigned yet' : 'Show savings not assigned yet'}>
              {showSavingsTile ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          )}
          <button className="btn-ghost btn-sm text-primary" onClick={() => setCreating(true)}><Plus size={14} /> New goal</button>
        </div>
      }
    >
      {isLoading ? <Loading /> : error || !data ? <ErrorNote error={error} /> : (
        <>
          {!shared && showSavingsTile && <SavingsTile a={data.allocation} />}
          {s && s.open_goals > 1 && (
            <div className={`mb-4 flex items-start gap-2 rounded-input px-3 py-2.5 text-[13px] ${s.combined_covered ? 'bg-positive-tint text-positive' : 'bg-warning-tint text-warning-ink'}`}>
              {s.combined_covered ? <Check size={16} className="mt-0.5 shrink-0" /> : <AlertTriangle size={16} className="mt-0.5 shrink-0" />}
              <p>
                <strong>Together</strong>, your {s.open_goals} open goals need <strong className="num">{fmtMoney(s.total_required_pace)}</strong> a month;
                the forecast expects you to save <strong className="num">{fmtMoney(s.expected_monthly_savings)}</strong>.{' '}
                {s.combined_covered ? 'That covers all of them.' : <>That is <strong className="num">{fmtMoney(s.combined_shortfall)}</strong> short — each card checks its goal on its own, so look at this total too.</>}
              </p>
            </div>
          )}
          {data.goals.length ? (
            <div className="flex flex-col">
              {data.goals.map((g) => (
                <GoalCard key={g.id} goal={g} today={today} unassigned={data.allocation.unassigned} extra={shareLine?.(g.id)} />
              ))}
            </div>
          ) : (
            <EmptyState title="No goals yet">{shared ? 'Saving for something together? Add it as a goal.' : 'Saving for a laptop, a trip or a safety buffer? Add it as a goal.'}</EmptyState>
          )}
        </>
      )}
      {creating && <GoalForm open today={today} onClose={() => setCreating(false)} />}
    </Card>
  );
}

/**
 * "Savings": what you saved this year that is not yet put toward a goal.
 * It goes down every time you add money to a goal. All three numbers come from
 * the backend (services/goals.py → allocation).
 */
function SavingsTile({ a }: { a: Allocation }) {
  const over = a.over_assigned;
  return (
    <div className={`mb-4 space-y-3 rounded-card border px-4 py-3 ${over ? 'border-warning bg-warning-tint' : 'border-line bg-positive-tint'}`}>
      <div>
        <div className="flex items-center gap-1.5 text-xs font-medium text-ink-soft">
          <PiggyBank size={14} /> Savings · not assigned yet
        </div>
        <div className={`num mt-1 text-kpi ${over ? 'text-warning-ink' : 'text-positive'}`}>
          {fmtMoney(a.unassigned)}
        </div>
        <div className="mt-0.5 text-xs text-ink-muted">
          {over ? '⚠ More is assigned to goals than you saved this year' : 'Free to add to a goal — or to keep as a buffer'}
        </div>
      </div>
      <dl className="num grid grid-cols-2 gap-4 border-t border-line/80 pt-3 text-sm">
        <div>
          <dt className="text-xs text-ink-muted">Saved in {a.year}</dt>
          <dd className="mt-0.5 font-medium">{fmtSigned(a.saved_this_year)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Put toward goals in {a.year}</dt>
          <dd className="mt-0.5 font-medium">{a.assigned ? fmtExpense(a.assigned) : fmtMoney(0)}</dd>
        </div>
      </dl>
    </div>
  );
}
