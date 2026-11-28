import { Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useAddBill, useBills, useCategories, useDeleteBill, useDismissBill, useGoals } from '../../api/queries';
import { Card } from '../../components/ui/Card';
import { ErrorNote } from '../../components/ui/Feedback';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { fmtDate, fmtExpense, fmtMoney, parseAmount } from '../../lib/format';

const RHYTHMS: [number, string][] = [[1, 'Monthly'], [3, 'Every 3 months'], [6, 'Every semester'], [12, 'Yearly']];
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/**
 * Bills the backend thinks repeat (same payee, same amount, regular rhythm).
 * One small card each, above the Recurring bills card.
 */
export function BillSuggestions() {
  const { data } = useBills();
  const add = useAddBill();
  const dismiss = useDismissBill();
  if (!data?.suggestions.length) return null;
  return (
    <>
      {data.suggestions.map((s) => (
        <section key={s.key} className="flex flex-col gap-2.5 rounded-card border border-line bg-surface px-4 py-3.5 shadow-card" data-testid="bill-suggestion">
          <span className="self-start"><StatusBadge kind="info">Suggestion</StatusBadge></span>
          <p className="text-body text-ink">
            <b className="font-semibold">“{s.name}” looks like a {s.rhythm_word} bill</b>{' '}
            <span className="num text-ink-soft">— {s.payments} payments of about {fmtMoney(s.amount)}.</span>
          </p>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" disabled={add.isPending} onClick={() => add.mutate({
              name: s.name, amount: s.amount, category: s.category, rhythm_months: s.rhythm_months, next_due: s.next_due, match: s.match, goal_id: null,
            })}>Add as a bill</button>
            <button type="button" className="btn-ghost text-ink-soft" onClick={() => dismiss.mutate(s.key)}>No thanks</button>
          </div>
          <ErrorNote error={add.error || dismiss.error} />
        </section>
      ))}
    </>
  );
}

/**
 * Recurring bills: what comes back and when it is due. Due dates move on by
 * themselves once a matching payment is recorded (services/recurring.py).
 */
export function RecurringBillsCard({ year }: { year: number }) {
  const { data } = useBills();
  const categories = useCategories(year);
  const goals = useGoals(year);
  const add = useAddBill();
  const del = useDeleteBill();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('');
  const [rhythm, setRhythm] = useState(1);
  const [due, setDue] = useState('');
  const [match, setMatch] = useState('');
  const [goalId, setGoalId] = useState<number | ''>('');
  const parsed = parseAmount(amount);
  const valid = name.trim() && parsed !== null && parsed > 0 && category.trim() && due;
  const funds = (goals.data?.goals ?? []).filter((g) => g.goal_type === 'sinking' && g.user_status === 'active');

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    add.mutate(
      { name: name.trim(), amount: parsed!, category: category.trim(), rhythm_months: rhythm, next_due: due, match: match.trim(), goal_id: goalId === '' ? null : goalId },
      { onSuccess: () => { setName(''); setAmount(''); setCategory(''); setDue(''); setMatch(''); setGoalId(''); setAdding(false); } },
    );
  };

  return (
    <Card title="Recurring bills" testId="recurring-bills" bodyClassName="!pt-1">
      <ul>
        {data?.bills.map((b) => (
          <li key={b.id} className="group grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 gap-y-0.5 border-b border-line py-2 text-[13px]">
            <span className="truncate font-medium text-ink">{b.name}</span>
            <span className="num text-right text-ink">{fmtExpense(b.amount)}</span>
            <button type="button" className="btn-icon row-span-2 h-7 opacity-0 focus:opacity-100 group-hover:opacity-100"
              aria-label={`Delete bill ${b.name}`} onClick={() => del.mutate(b.id)}>
              <Trash2 size={13} aria-hidden />
            </button>
            <span className="num truncate text-label text-ink-soft" title={b.last_paid ? `Last paid ${fmtDate(b.last_paid)}` : undefined}>
              {cap(b.rhythm_word)} · next {fmtDate(b.due, { short: true })}
            </span>
            <span className="text-right text-label text-ink-soft">
              {b.goal_name ? `Paid from sinking fund “${b.goal_name}”` : 'Paid from liquidity'}
            </span>
          </li>
        ))}
        {data && !data.bills.length && <li className="py-2 text-[13px] text-ink-soft">No recurring bills yet.</li>}
      </ul>

      {adding ? (
        <form onSubmit={submit} className="mt-3 space-y-2">
          <div className="flex gap-2">
            <input className="input" placeholder="Bill name" aria-label="Bill name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            <input className="input num w-24" inputMode="decimal" placeholder="€" aria-label="Bill amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div className="flex gap-2">
            <input className="input" placeholder="Category" list="bill-cats" aria-label="Bill category" value={category} onChange={(e) => setCategory(e.target.value)} />
            <datalist id="bill-cats">{categories.data?.expense.map((c) => <option key={c.name} value={c.name} />)}</datalist>
            <select className="input w-36" aria-label="Bill rhythm" value={rhythm} onChange={(e) => setRhythm(Number(e.target.value))}>
              {RHYTHMS.map(([m, label]) => <option key={m} value={m}>{label}</option>)}
            </select>
          </div>
          <div className="flex gap-2">
            <input className="input num" type="date" aria-label="Next due date" value={due} onChange={(e) => setDue(e.target.value)} />
            <input className="input" placeholder="Payee contains (optional)" aria-label="Bill payee text" value={match} onChange={(e) => setMatch(e.target.value)} />
          </div>
          <select className="input" aria-label="Paid from sinking fund" value={goalId} onChange={(e) => setGoalId(e.target.value === '' ? '' : Number(e.target.value))}>
            <option value="">Paid from liquidity</option>
            {funds.map((g) => <option key={g.id} value={g.id}>From sinking fund “{g.name}”</option>)}
          </select>
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-ghost text-ink-soft" onClick={() => setAdding(false)}>Cancel</button>
            <button className="btn-primary" disabled={!valid || add.isPending} aria-label="Add bill">Add bill</button>
          </div>
        </form>
      ) : (
        <button type="button" className="btn-ghost -ml-3 mt-2" onClick={() => setAdding(true)}>+ Add bill</button>
      )}
      <ErrorNote error={add.error || del.error} />
    </Card>
  );
}
