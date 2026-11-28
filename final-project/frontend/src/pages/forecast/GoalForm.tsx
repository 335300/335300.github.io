import { useState } from 'react';
import { useCreateGoal, useUpdateGoal } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { Modal } from '../../components/ui/Modal';
import { parseAmount } from '../../lib/format';
import type { Goal, GoalType } from '../../lib/types';

const RHYTHMS = [
  { months: 1, label: 'Every month' },
  { months: 3, label: 'Every 3 months' },
  { months: 6, label: 'Every semester (6 months)' },
  { months: 12, label: 'Every year' },
];

export function GoalForm({ open, onClose, goal, today }: { open: boolean; onClose: () => void; goal?: Goal; today: string }) {
  const create = useCreateGoal();
  const update = useUpdateGoal();
  const [name, setName] = useState(goal?.name ?? '');
  const [target, setTarget] = useState(goal ? String(goal.target_amount) : '');
  const [deadline, setDeadline] = useState(goal?.target_date ?? '');
  const [notes, setNotes] = useState(goal?.notes ?? '');
  const [emergency, setEmergency] = useState(goal?.emergency_fund ?? false);
  const [goalType, setGoalType] = useState<GoalType>(goal?.goal_type ?? 'one_time');
  const [repeat, setRepeat] = useState(goal?.repeat_months ?? 6);
  // Spent on its date in the forecast? Follows the default (one-time, not the emergency fund) until ticked by hand.
  const [spendChoice, setSpendChoice] = useState<boolean | null>(goal?.spend_in_forecast ?? null);
  const sinking = goalType === 'sinking';
  const spend = spendChoice ?? (!sinking && !emergency);
  const parsed = parseAmount(target);
  const mutation = goal ? update : create;
  const valid = name.trim() && parsed !== null && parsed > 0 && deadline;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    const body = {
      name: name.trim(), target_amount: parsed!, target_date: deadline, notes: notes.trim(), emergency_fund: emergency,
      goal_type: goalType, repeat_months: sinking ? repeat : null,
      ...(spendChoice !== null ? { spend_in_forecast: spendChoice } : {}),
    };
    if (goal) update.mutate({ id: goal.id, patch: body }, { onSuccess: onClose });
    else create.mutate(body, { onSuccess: onClose });
  };

  return (
    <Modal title={goal ? 'Edit goal' : 'New savings goal'} open={open} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-1 rounded-lg bg-bg p-0.5" role="radiogroup" aria-label="Kind of goal">
          {([['one_time', 'Savings goal (one time)'], ['sinking', 'Sinking fund (repeats)']] as const).map(([value, label]) => (
            <button type="button" key={value} role="radio" aria-checked={goalType === value} onClick={() => setGoalType(value)}
              className={`rounded-md py-1.5 text-xs font-medium ${goalType === value ? 'bg-surface text-ink shadow-card' : 'text-ink-soft'}`}>
              {label}
            </button>
          ))}
        </div>
        {sinking && (
          <p className="text-xs text-ink-muted">
            A sinking fund puts a little aside each month for a bill that comes back (semester fee, yearly subscriptions).
            When the bill comes, “Pay from fund” records it and the fund starts the next cycle.
          </p>
        )}
        <div>
          <label className="label" htmlFor="goal-name">{sinking ? 'Which bill?' : 'What are you saving for?'}</label>
          <input id="goal-name" className="input" placeholder={sinking ? 'e.g. Semester fee' : 'e.g. New laptop'} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="goal-target">{sinking ? 'One bill (€)' : 'Target amount (€)'}</label>
            <input id="goal-target" inputMode="decimal" className="input num" placeholder="900" value={target} onChange={(e) => setTarget(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="goal-date">{sinking ? 'Next due date' : 'By when?'}</label>
            <input id="goal-date" type="date" className="input num" min={goal ? undefined : today} value={deadline} onChange={(e) => setDeadline(e.target.value)} />
          </div>
        </div>
        {sinking && (
          <div>
            <label className="label" htmlFor="goal-repeat">The bill comes back</label>
            <select id="goal-repeat" className="input" value={repeat} onChange={(e) => setRepeat(Number(e.target.value))}>
              {RHYTHMS.map((r) => <option key={r.months} value={r.months}>{r.label}</option>)}
            </select>
          </div>
        )}
        <div>
          <label className="label" htmlFor="goal-notes">Notes <span className="font-normal text-ink-muted">(optional)</span></label>
          <input id="goal-notes" className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <label className="flex items-start gap-2 text-sm">
          <input id="goal-emergency" type="checkbox" className="mt-0.5" checked={emergency} onChange={(e) => setEmergency(e.target.checked)} />
          <span>
            This is my emergency fund
            <span className="block text-xs text-ink-muted">The Overview then shows how many months of essential costs it covers. Only one goal can be the emergency fund.</span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input id="goal-spend" type="checkbox" className="mt-0.5" checked={spend} onChange={(e) => setSpendChoice(e.target.checked)} />
          <span>
            {sinking ? 'Take each bill out of the forecast balance on its due date' : 'Spend it on its date in the forecast'}
            <span className="block text-xs text-ink-muted">
              {sinking
                ? 'Leave it off when the bill is already in your budget plan, so it is not counted twice.'
                : 'The forecast then takes the money out of your balance in that month. Leave it off for money that stays (an emergency fund).'}
            </span>
          </span>
        </label>
        <p className="text-xs text-ink-muted">
          Progress comes from contributions you log (“I put €200 toward this”), separate from your transactions — so
          nothing is counted twice.
        </p>
        <ErrorNote error={mutation.error} />
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={!valid || mutation.isPending}>{goal ? 'Save' : 'Create goal'}</button>
        </div>
      </form>
    </Modal>
  );
}
