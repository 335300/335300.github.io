import { AlertTriangle, CalendarCheck, ChevronDown, ChevronRight, LifeBuoy, MoreHorizontal, Plus, Receipt, Repeat, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useAddContribution, useDeleteContribution, useDeleteGoal, usePayFromFund, useUpdateGoal } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { Modal } from '../../components/ui/Modal';
import { ProgressBar } from '../../components/ui/ProgressBar';
import { GoalBadge } from '../../components/ui/StatusBadge';
import { fmtDate, fmtMoney, fmtPct, parseAmount } from '../../lib/format';
import type { Goal } from '../../lib/types';
import { GoalForm } from './GoalForm';

export function GoalCard({ goal, today, unassigned, extra }: {
  goal: Goal;
  today: string;
  unassigned: number;
  /** An extra data line under the goal (Joint: each person's part). */
  extra?: React.ReactNode;
}) {
  const [adding, setAdding] = useState(false);
  const [history, setHistory] = useState(false);
  const [menu, setMenu] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [paying, setPaying] = useState(false);
  const sinking = goal.goal_type === 'sinking';
  const updateGoal = useUpdateGoal();
  const deleteGoal = useDeleteGoal();
  const delContribution = useDeleteContribution();
  const finished = goal.status === 'completed' || goal.status === 'abandoned';
  const met = goal.status === 'met';

  return (
    <article className={`relative flex flex-col gap-1.5 border-b border-line py-3.5 first:pt-0 last:border-0 last:pb-0 ${finished ? 'opacity-75' : ''}`}
      data-testid={`goal-${goal.id}`}>
      <header className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="flex flex-wrap items-center gap-1.5 text-[13px] font-semibold">
            {goal.name}
            {goal.emergency_fund && (
              <span className="chip h-[18px] gap-1 bg-primary-tint text-primary"><LifeBuoy size={11} aria-hidden /> Emergency fund</span>
            )}
            {sinking && (
              <span className="chip h-[18px] gap-1"><Repeat size={11} aria-hidden /> Every {goal.repeat_months === 1 ? 'month' : `${goal.repeat_months} months`}</span>
            )}
          </h3>
        </div>
        <span className="num shrink-0 text-[13px] text-ink-soft">{fmtMoney(goal.saved)} of {fmtMoney(goal.target_amount)}</span>
        <div className="relative -mr-1 -mt-1">
          <button className="btn-icon btn-sm h-6 w-6" aria-label="Goal actions" onClick={() => setMenu((m) => !m)}><MoreHorizontal size={15} /></button>
          {menu && (
            <div className="absolute right-0 top-7 z-20 w-44 rounded-lg border border-line bg-surface-raised py-1 text-sm shadow-pop" onMouseLeave={() => setMenu(false)}>
              <MenuItem onClick={() => { setEditing(true); setMenu(false); }}>Edit goal</MenuItem>
              {goal.user_status === 'active' ? (
                <>
                  <MenuItem onClick={() => { updateGoal.mutate({ id: goal.id, patch: { status: 'completed' } }); setMenu(false); }}>Mark as completed</MenuItem>
                  <MenuItem onClick={() => { updateGoal.mutate({ id: goal.id, patch: { status: 'abandoned' } }); setMenu(false); }}>Stop this goal</MenuItem>
                </>
              ) : (
                <MenuItem onClick={() => { updateGoal.mutate({ id: goal.id, patch: { status: 'active' } }); setMenu(false); }}>Make active again</MenuItem>
              )}
              <MenuItem danger onClick={() => { setConfirmDelete(true); setMenu(false); }}>Delete…</MenuItem>
            </div>
          )}
        </div>
      </header>

      <ProgressBar pct={goal.progress_pct} reached={met} tone={finished ? 'neutral' : 'secondary'} label={`${goal.name} progress`} />

      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-label text-ink-soft">
          <GoalBadge status={goal.status} />
          <span className="num">
            {sinking ? 'next bill ' : 'by '}{fmtDate(goal.target_date)}
            {!finished && !met && goal.months_remaining > 0 && ` · ${goal.months_remaining} month${goal.months_remaining === 1 ? '' : 's'} left`}
            {sinking && goal.monthly_set_aside !== null && <> · {fmtMoney(goal.monthly_set_aside)} a month covers it</>}
          </span>
        </span>
        <span className="num shrink-0 text-label text-ink-soft">{fmtPct(goal.progress_pct)} saved</span>
      </div>

      <div className="text-label leading-relaxed">
        <StatusExplanation goal={goal} onEdit={() => setEditing(true)} onComplete={() => updateGoal.mutate({ id: goal.id, patch: { status: 'completed' } })} />
        {extra && !finished && <p className="mt-1 text-ink-soft">{extra}</p>}
        {!finished && <ForecastCheck goal={goal} />}
      </div>

      {confirmDelete && (
        <div className="flex items-center gap-2 rounded-input bg-negative-tint px-3 py-2 text-label text-negative">
          <span className="flex-1">Delete “{goal.name}” and its {goal.contributions.length} contribution(s)?</span>
          <button className="btn-secondary btn-sm" onClick={() => setConfirmDelete(false)}>Keep</button>
          <button className="btn-danger btn-sm" onClick={() => deleteGoal.mutate(goal.id)}>Delete</button>
        </div>
      )}

      <div>
        {adding ? (
          <ContributionForm goal={goal} today={today} unassigned={unassigned} onDone={() => setAdding(false)} />
        ) : (
          <div className="flex items-center justify-between">
            <button className="btn-ghost btn-sm -ml-2" onClick={() => setHistory((h) => !h)} disabled={!goal.contributions.length} aria-expanded={history}>
              {history ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              {goal.contributions.length} contribution{goal.contributions.length === 1 ? '' : 's'}
            </button>
            {!finished && (
              <span className="flex gap-1.5">
                {sinking && (
                  <button className="btn-ghost btn-sm" onClick={() => setPaying(true)}><Receipt size={13} /> Pay from fund</button>
                )}
                <button className="btn-ghost btn-sm text-primary" onClick={() => setAdding(true)}><Plus size={13} /> Add money</button>
              </span>
            )}
          </div>
        )}
        {history && !adding && (
          <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto">
            {goal.contributions.map((c) => (
              <li key={c.id} className="group flex items-center gap-2 text-xs">
                <span className="num w-20 text-ink-muted">{fmtDate(c.date, { short: true })}</span>
                <span className="flex-1 truncate text-ink-soft">{c.note || '—'}</span>
                <span className={`num font-medium ${c.withdrawal ? 'text-ink' : 'text-secondary'}`}>
                  {c.withdrawal ? `−${fmtMoney(c.amount)}` : `+${fmtMoney(c.amount)}`}
                </span>
                <button className="btn-ghost btn-sm h-5 px-1 opacity-0 group-hover:opacity-100" aria-label="Remove contribution"
                  onClick={() => delContribution.mutate({ goalId: goal.id, id: c.id })}><Trash2 size={11} /></button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <ErrorNote error={updateGoal.error || deleteGoal.error || delContribution.error} />
      {editing && <GoalForm open goal={goal} today={today} onClose={() => setEditing(false)} />}
      {paying && <PayFromFundModal goal={goal} today={today} onClose={() => setPaying(false)} />}
    </article>
  );
}

function StatusExplanation({ goal, onEdit, onComplete }: { goal: Goal; onEdit: () => void; onComplete: () => void }) {
  const pace = goal.required_monthly_pace;
  switch (goal.status) {
    case 'on_track':
      return (
        <p className="text-ink-soft">
          Needs <strong className="num text-ink">{fmtMoney(pace ?? 0)}</strong> a month. Your forecast expects you to save{' '}
          <strong className="num text-ink">{fmtMoney(goal.expected_monthly_savings)}</strong> a month, so this fits.
        </p>
      );
    case 'behind':
      return (
        <p className="text-ink-soft">
          Needs <strong className="num text-ink">{fmtMoney(pace ?? 0)}</strong> a month, but the forecast expects{' '}
          <strong className="num text-ink">{fmtMoney(goal.expected_monthly_savings)}</strong>.{' '}
          <span className="text-warning-ink">⚠ About <strong className="num">{fmtMoney(goal.shortfall)}</strong> more per month</span> —
          trim a variable budget, or{' '}
          <button className="font-medium text-primary underline-offset-2 hover:underline" onClick={onEdit}>move the deadline</button>.
        </p>
      );
    case 'overdue':
      return (
        <p className="text-negative">
          The deadline passed with <strong className="num">{fmtMoney(goal.remaining)}</strong> still to go.{' '}
          <span className="text-ink-soft">Next step: </span>
          <button className="font-medium text-primary underline-offset-2 hover:underline" onClick={onEdit}>set a new date or target</button>.
        </p>
      );
    case 'met':
      if (goal.goal_type === 'sinking') {
        return (
          <p className="text-ink-soft">
            <span className="font-medium text-positive">✓ The next bill is covered.</span> When it comes, use “Pay from fund”.
          </p>
        );
      }
      return (
        <p className="text-ink-soft">
          <span className="font-medium text-positive">✓ You reached it!</span> Well done.{' '}
          <button className="font-medium text-primary underline-offset-2 hover:underline" onClick={onComplete}>Mark as completed</button>{' '}
          to move it out of your active goals.
        </p>
      );
    case 'completed':
      return <p className="text-ink-muted">Completed — no longer counted in your monthly plan.</p>;
    default:
      return <p className="text-ink-muted">Stopped — no longer counted in your monthly plan.</p>;
  }
}

function ContributionForm({ goal, today, unassigned, onDone }: { goal: Goal; today: string; unassigned: number; onDone: () => void }) {
  const add = useAddContribution();
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(today);
  const [note, setNote] = useState('');
  const parsed = parseAmount(amount);
  const valid = parsed !== null && parsed > 0 && date;
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) add.mutate({ goalId: goal.id, body: { amount: parsed!, date, note: note.trim() } }, { onSuccess: onDone });
      }}
    >
      <div className="grid grid-cols-2 gap-2">
        <input className="input h-8 num" inputMode="decimal" placeholder="Amount €" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus aria-label="Contribution amount" />
        <input className="input h-8 num" type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Contribution date" />
      </div>
      <input className="input h-8" placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Note" />
      {valid && parsed! > unassigned && (
        <p className="rounded-input bg-warning-tint px-2.5 py-1.5 text-label text-warning-ink" role="status">
          ⚠ This is more than your unassigned savings ({fmtMoney(unassigned)}). You can still add it — for example from
          money you had before this year.
        </p>
      )}
      <ErrorNote error={add.error} />
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-ghost btn-sm" onClick={onDone}>Cancel</button>
        <button type="submit" className="btn-primary btn-sm" disabled={!valid || add.isPending}>Add to {goal.name}</button>
      </div>
    </form>
  );
}

function MenuItem({ children, onClick, danger }: { children: React.ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button className={`block w-full px-3 py-1.5 text-left hover:bg-neutral-tint ${danger ? 'text-negative' : 'text-ink'}`} onClick={onClick}>
      {children}
    </button>
  );
}

/** Pay a sinking fund's bill: the backend records the expense and takes the money out of the fund. */
function PayFromFundModal({ goal, today, onClose }: { goal: Goal; today: string; onClose: () => void }) {
  const pay = usePayFromFund();
  const [date, setDate] = useState(today);
  const [amount, setAmount] = useState(String(goal.target_amount));
  const [category, setCategory] = useState(goal.name);
  const [desc, setDesc] = useState('');
  const parsed = parseAmount(amount);
  const valid = parsed !== null && parsed > 0 && date && category.trim();
  return (
    <Modal title={`Pay from “${goal.name}”`} open onClose={onClose}>
      <form className="space-y-3 text-sm" onSubmit={(e) => {
        e.preventDefault();
        if (valid) pay.mutate({ goalId: goal.id, body: { date, amount: parsed!, category: category.trim(), desc: desc.trim() } }, { onSuccess: onClose });
      }}>
        <p className="text-xs text-ink-muted">
          This records the bill as an expense and takes the same amount out of the fund (up to the{' '}
          <span className="num">{fmtMoney(goal.saved)}</span> it holds), so your liquidity does not drop. The next bill is then
          due {goal.repeat_months === 1 ? 'a month' : `${goal.repeat_months} months`} later.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="pay-amount">Bill amount (€)</label>
            <input id="pay-amount" inputMode="decimal" className="input num" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="pay-date">Paid on</label>
            <input id="pay-date" type="date" className="input num" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="pay-cat">Expense category</label>
          <input id="pay-cat" className="input" value={category} onChange={(e) => setCategory(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="pay-desc">Description <span className="font-normal text-ink-muted">(optional)</span></label>
          <input id="pay-desc" className="input" value={desc} onChange={(e) => setDesc(e.target.value)} />
        </div>
        <ErrorNote error={pay.error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={!valid || pay.isPending}>Pay the bill</button>
        </div>
      </form>
    </Modal>
  );
}

/** The goal seen through the 12-month forecast — every figure from the backend. */
function ForecastCheck({ goal }: { goal: Goal }) {
  const f = goal.forecast;
  if (!f) {
    return (
      <p className="mt-1 text-ink-soft" data-testid={`goal-forecast-${goal.id}`}>
        {goal.spends_in_forecast ? 'Bought after the 12 months the forecast shows.' : 'Kept in the account — not spent in the forecast.'}
      </p>
    );
  }
  const where = f.line ? ` (${f.line})` : '';
  return (
    <p className={`mt-1 flex items-start gap-1.5 ${f.affordable ? 'text-ink-soft' : 'text-warning-ink'}`} data-testid={`goal-forecast-${goal.id}`}>
      {f.affordable ? <CalendarCheck size={13} className="mt-0.5 shrink-0" /> : <AlertTriangle size={13} className="mt-0.5 shrink-0" />}
      <span>
        {f.spent ? (
          <>Forecast: bought in {f.month_name}; the balance is then{' '}
            <strong className="num">{fmtMoney(f.balance)}</strong>{where}
            {f.affordable ? ' — affordable.' : ' — the account would go below zero.'}</>
        ) : (
          <>Forecast: in {f.month_name} the balance is <strong className="num">{fmtMoney(f.balance)}</strong>{where}
            {f.affordable ? ', enough to hold this goal.' : ', less than this goal needs to hold.'}</>
        )}
      </span>
    </p>
  );
}
