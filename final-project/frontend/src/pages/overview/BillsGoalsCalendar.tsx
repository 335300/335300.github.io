import { CalendarClock, CircleAlert, CircleCheck, Clock, Flag, X } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { useBillsCalendar } from '../../api/queries';
import { Card, EmptyState, Hint } from '../../components/ui/Card';
import { ErrorNote } from '../../components/ui/Feedback';
import { MonthGrid, MonthNav } from '../../components/ui/MonthGrid';
import { ProgressBar } from '../../components/ui/ProgressBar';
import { GoalBadge } from '../../components/ui/StatusBadge';
import { fmtDate, fmtMoney, MONTHS } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { CalendarBill, CalendarGoal, Dashboard } from '../../lib/types';

type Look = { cls: string; icon: ReactNode; word: string };

/** Every state has an icon and a word (in the legend and the day details), never colour alone. */
function billLook(b: CalendarBill): Look {
  if (b.paid) return { cls: 'text-ink-muted', icon: <CircleCheck size={11} />, word: 'Paid' };
  if (b.overdue) return { cls: 'bg-negative-tint text-negative', icon: <CircleAlert size={11} />, word: 'Overdue' };
  if (b.ready === true) return { cls: 'bg-positive-tint text-positive', icon: <CircleCheck size={11} />, word: 'Money ready' };
  if (b.ready === false) return { cls: 'bg-warning-tint text-warning', icon: <CircleAlert size={11} />, word: 'Short' };
  return { cls: 'bg-bg text-ink-soft', icon: <Clock size={11} />, word: 'Planned' };
}

function billDetail(b: CalendarBill): string {
  if (b.paid) return b.paid_on ? `Paid on ${fmtDate(b.paid_on, { short: true })}` : 'Paid';
  if (b.ready === false) return `${fmtMoney(b.short_by)} short`;
  return billLook(b).word;
}

const GOAL_LOOK: Look = { cls: 'bg-secondary-tint text-secondary', icon: <Flag size={11} />, word: 'Goal deadline' };

const LEGEND: Look[] = [
  { cls: 'text-positive', icon: <CircleCheck size={12} />, word: 'Money ready' },
  { cls: 'text-warning', icon: <CircleAlert size={12} />, word: 'Short' },
  { cls: 'text-negative', icon: <CircleAlert size={12} />, word: 'Overdue' },
  { cls: 'text-ink-soft', icon: <Clock size={12} />, word: 'Planned' },
  { cls: 'text-ink-muted', icon: <CircleCheck size={12} />, word: 'Paid' },
  { cls: 'text-secondary', icon: <Flag size={12} />, word: 'Goal deadline' },
];

/**
 * "Upcoming 30 days" and "Savings goals" in one card: a month calendar with the
 * bills due (from services/recurring.py → month_calendar) and each goal's
 * deadline, and beside it the goals with their progress.
 */
export function BillsGoalsCalendar({ data }: { data: Dashboard }) {
  const [ym, setYm] = useState({ y: data.year, m: data.month });
  const [day, setDay] = useState<string | null>(null);
  const cal = useBillsCalendar(ym.y, ym.m);
  const setTab = useUi((s) => s.setTab);
  const move = (step: number) => {
    const n = ym.y * 12 + ym.m + step;
    setYm({ y: Math.floor(n / 12), m: n % 12 });
    setDay(null);
  };

  const bills = cal.data?.bills ?? [];
  const goals = cal.data?.goals ?? [];
  const billsOn = (iso: string) => bills.filter((b) => b.due === iso);
  const goalsOn = (iso: string) => goals.filter((g) => g.date === iso);

  return (
    <Card
      title={<span className="flex items-center gap-1.5"><CalendarClock size={15} /> Upcoming bills & savings goals</span>}
      collapseKey="overview-calendar"
      collapseLabel="Upcoming bills & savings goals"
      action={<button className="btn-ghost btn-sm" onClick={() => setTab('forecast')}>Manage goals</button>}
    >
      <div className="grid grid-cols-12 gap-5" data-testid="bills-goals-calendar">
        <div className="col-span-8">
          <div className="mb-2 flex items-center justify-between gap-3">
            <MonthNav year={ym.y} month={ym.m} onPrev={() => move(-1)} onNext={() => move(1)} />
            {cal.data && (
              <div className="num flex gap-4 text-xs text-ink-soft">
                <span>Due in {MONTHS[ym.m]} <strong className="text-ink">{fmtMoney(cal.data.total_due)}</strong></span>
                {cal.data.total_paid > 0 && <span>Paid <strong className="text-ink">{fmtMoney(cal.data.total_paid)}</strong></span>}
              </div>
            )}
          </div>
          {cal.error ? <ErrorNote error={cal.error} /> : (
            <MonthGrid
              year={ym.y}
              month={ym.m}
              today={cal.data?.today ?? ''}
              selected={day}
              onDayClick={(iso) => setDay(iso === day ? null : iso)}
              cellClassName="min-h-[72px]"
              renderDay={(iso) => (
                <>
                  {billsOn(iso).map((b) => <Chip key={`b${b.bill_id}`} look={billLook(b)} label={b.name}
                    amount={fmtMoney(b.amount, { round: true })} title={`${b.name} · ${fmtMoney(b.amount)} · ${billDetail(b)}`} />)}
                  {goalsOn(iso).map((g) => <Chip key={`g${g.goal_id}`} look={GOAL_LOOK} label={g.name}
                    title={`${g.name} · goal deadline · ${fmtMoney(g.target_amount)}`} />)}
                </>
              )}
            />
          )}
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-soft" aria-label="Legend">
            {LEGEND.map((l) => (
              <li key={l.word} className="flex items-center gap-1"><span className={l.cls}>{l.icon}</span>{l.word}</li>
            ))}
          </ul>
          {day && <DayDetails day={day} bills={billsOn(day)} goals={goalsOn(day)} onClose={() => setDay(null)} />}
        </div>
        <div className="col-span-4 border-l border-line pl-5">
          <GoalsList data={data} />
        </div>
      </div>
    </Card>
  );
}

function Chip({ look, label, amount, title }: { look: Look; label: string; amount?: string; title: string }) {
  return (
    <div className={`flex items-center gap-1 rounded px-1 py-px text-xs leading-tight ${look.cls}`} title={title}>
      <span className="shrink-0">{look.icon}</span>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {amount && <span className="num shrink-0">{amount}</span>}
    </div>
  );
}

function DayDetails({ day, bills, goals, onClose }: {
  day: string;
  bills: CalendarBill[];
  goals: CalendarGoal[];
  onClose: () => void;
}) {
  return (
    <div className="mt-3 rounded-lg border border-line p-3" data-testid="calendar-day">
      <div className="mb-1 flex items-center">
        <h3 className="flex-1 text-sm font-semibold">{fmtDate(day)}</h3>
        <button className="btn-ghost btn-sm" aria-label="Close day" onClick={onClose}><X size={14} /></button>
      </div>
      {!bills.length && !goals.length ? (
        <p className="text-sm text-ink-muted">No bills or goal deadlines on this day.</p>
      ) : (
        <ul className="divide-y divide-line/70 text-sm">
          {bills.map((b) => {
            const look = billLook(b);
            return (
              <li key={b.bill_id} className="flex items-center gap-3 py-1.5">
                <span className="flex-1 truncate">
                  {b.name}
                  {!b.paid && <span className="block text-xs text-ink-muted">{b.goal_name ? `from “${b.goal_name}”` : 'from your liquidity'}</span>}
                </span>
                <span className="num w-24 text-right">{fmtMoney(b.amount)}</span>
                <span className={`inline-flex w-36 items-center justify-end gap-1 text-xs font-medium ${look.cls.replace(/bg-\S+/, '')}`}>
                  {look.icon} <span className="num">{billDetail(b)}</span>
                </span>
              </li>
            );
          })}
          {goals.map((g) => (
            <li key={g.goal_id} className="flex items-center gap-3 py-1.5">
              <span className="flex-1 truncate">{g.name}</span>
              <span className="num w-24 text-right">{fmtMoney(g.target_amount)}</span>
              <span className="inline-flex w-36 items-center justify-end gap-1 text-xs font-medium text-secondary"><Flag size={11} /> Goal deadline</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function GoalsList({ data }: { data: Dashboard }) {
  const { goals, summary } = data.goals;
  const k = data.kpis;
  return (
    <div>
      <h3 className="text-sm font-semibold">Savings goals</h3>
      {goals.length > 0 && (
        <p className="num mt-0.5 text-xs text-ink-muted">{fmtMoney(k.earmarked)} of your balance is saved for goals · {fmtMoney(k.liquidity)} is liquid</p>
      )}
      {goals.length ? (
        <>
          <ul className="mt-2 divide-y divide-line/70">
            {goals.map((g) => (
              <li key={g.id} className="py-2.5">
                <div className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{g.name}</span>
                  <GoalBadge status={g.status} />
                </div>
                <div className="mt-1.5">
                  <ProgressBar pct={g.progress_pct} tone={g.status === 'met' ? 'positive' : 'secondary'} height="h-1.5" label={`${g.name} progress`} />
                </div>
                <div className="num mt-1 flex flex-wrap gap-x-3 text-xs text-ink-muted">
                  <span><strong className="font-medium text-ink">{fmtMoney(g.saved)}</strong> of {fmtMoney(g.target_amount)}</span>
                  <span>by {fmtDate(g.target_date)}</span>
                  {g.required_monthly_pace !== null && g.remaining > 0 && <span>needs {fmtMoney(g.required_monthly_pace)} a month</span>}
                  {g.added_this_month > 0 && <span className="font-medium text-secondary">+{fmtMoney(g.added_this_month)} in {data.month_name}</span>}
                </div>
              </li>
            ))}
          </ul>
          {summary.open_goals > 0 && (
            <div className="border-t border-line pt-3">
              <Hint>
                Your open goals need <strong className="num text-ink">{fmtMoney(summary.total_required_pace)}</strong> a month; the
                forecast expects you to keep <strong className="num text-ink">{fmtMoney(summary.expected_monthly_savings)}</strong>.
                {summary.combined_covered ? ' That covers them.' : ` That is ${fmtMoney(summary.combined_shortfall)} short.`}
              </Hint>
            </div>
          )}
        </>
      ) : (
        <div className="mt-2"><EmptyState title="No goals yet">Add one in the Forecast tab.</EmptyState></div>
      )}
    </div>
  );
}
