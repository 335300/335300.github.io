import { Pencil, Plus, Sprout, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useAddTransactionAnyYear, useDeleteInvestment } from '../../api/queries';
import { ErrorNote } from '../ui/Feedback';
import { ProgressBar } from '../ui/ProgressBar';
import { StatusBadge } from '../ui/StatusBadge';
import { fmtDate, fmtLocal, fmtMoney, fmtMonthYear, fmtPct, MONTHS, parseAmount } from '../../lib/format';
import type { InvestmentPlan } from '../../lib/types';
import { InvestmentForm } from './InvestmentForm';

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

/**
 * One investment plan: how far it is, what is left, and this month's payment.
 * Every number is computed by the backend (services/investments.py).
 */
export function InvestmentCard({ plan, year, month, today, manage = false }: {
  plan: InvestmentPlan;
  year: number;
  month: number;
  today: string;
  manage?: boolean;
}) {
  const [paying, setPaying] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [history, setHistory] = useState(false);
  const remove = useDeleteInvestment();
  const done = plan.status === 'completed';
  const approx = (v: number | null) => (v === null ? null : `≈ ${fmtMoney(v, { round: true })}`);

  return (
    <article className={`flex flex-col rounded-card border bg-surface p-5 shadow-card ${done ? 'border-gold' : 'border-line'}`}>
      <header className="flex items-start gap-2">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-invest-tint text-invest" aria-hidden><Sprout size={16} /></span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-card-title">{plan.name}</h3>
          <p className="text-label text-ink-soft">
            {plural(plan.total_installments, plan.unit)} of {fmtLocal(plan.installment_amount, plan.local_currency)}
            {plan.cost_per_installment ? ` (≈ ${fmtMoney(plan.cost_per_installment, { round: true })})` : ''}
          </p>
        </div>
        {plan.invested_month > 0 ? (
          <StatusBadge kind="positive">Paid in {MONTHS[month]}</StatusBadge>
        ) : (
          !done && (
            <StatusBadge kind="neutral">No payment in {MONTHS[month]}</StatusBadge>
          )
        )}
      </header>

      <div className="mt-3">
        <div className="mb-1.5 flex items-baseline justify-between">
          <span className="num text-kpi">{plan.paid} <span className="text-body font-normal text-ink-soft">of {plural(plan.total_installments, plan.unit)} paid</span></span>
          <span className="num text-label text-ink-soft">{fmtPct(plan.progress_pct, 1)}</span>
        </div>
        <ProgressBar pct={plan.progress_pct} tone={done ? 'positive' : 'invest'} label={`${plan.name} progress`} />
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2.5 text-sm">
        <Fact label="Built so far" value={fmtLocal(plan.paid_local, plan.local_currency)} sub={approx(plan.value_at_cost)} />
        <Fact label="Still to pay" value={fmtLocal(plan.remaining_local, plan.local_currency)} sub={approx(plan.remaining_cost)} />
        <Fact
          label={`Paid in ${MONTHS[month]}`}
          value={fmtMoney(plan.invested_month)}
          sub={plan.installments_month ? plural(plan.installments_month, plan.unit) : `${fmtMoney(plan.invested_year)} in ${year}`}
        />
        <Fact
          label={`Last ${plan.unit}`}
          value={plan.expected_end ? fmtMonthYear(plan.expected_end) : 'Done'}
          sub={plan.expected_end ? `${plural(plan.remaining, plan.unit)} to go, one a month` : 'Fully paid'}
        />
      </dl>

      {confirmDelete && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-negative-tint px-3 py-2 text-[13px] text-ink">
          <span className="flex-1">Remove “{plan.name}”? Its payments stay in your transactions.</span>
          <button className="btn-secondary btn-sm" onClick={() => setConfirmDelete(false)}>Keep</button>
          <button className="btn-danger-solid btn-sm" onClick={() => remove.mutate(plan.id)}>Remove</button>
        </div>
      )}

      <div className="mt-3 border-t border-line pt-3">
        {paying ? (
          <PaymentForm plan={plan} today={today} onDone={() => setPaying(false)} />
        ) : (
          <div className="flex items-center gap-1">
            <button className="btn-ghost btn-sm -ml-2" onClick={() => setHistory((h) => !h)} disabled={!plan.payments.length}>
              {plural(plan.payments.length, 'recent payment')}
            </button>
            <span className="flex-1" />
            {manage && (
              <>
                <button className="btn-icon btn-sm" aria-label={`Edit ${plan.name}`} onClick={() => setEditing(true)}><Pencil size={14} aria-hidden /></button>
                <button className="btn-icon btn-sm" aria-label={`Remove ${plan.name}`} onClick={() => setConfirmDelete(true)}><Trash2 size={14} aria-hidden /></button>
              </>
            )}
            {!done && <button className="btn-secondary btn-sm" onClick={() => setPaying(true)}><Plus size={14} aria-hidden /> Record a payment</button>}
          </div>
        )}
        {history && !paying && (
          <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto">
            {plan.payments.map((p) => (
              <li key={`${p.year}-${p.id}`} className="flex items-center gap-2 text-table">
                <span className="num w-24 text-ink-soft">{fmtDate(p.date)}</span>
                <span className="flex-1 truncate text-ink-soft">{p.desc || '—'}</span>
                <span className="num text-ink-soft">{p.installments ? plural(p.installments, plan.unit) : 'not counted'}</span>
                <span className="num w-20 text-right font-medium">{fmtMoney(p.amount)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <ErrorNote error={remove.error} />
      {editing && <InvestmentForm open plan={plan} year={year} onClose={() => setEditing(false)} />}
    </article>
  );
}

function Fact({ label, value, sub }: { label: string; value: string; sub?: string | null }) {
  return (
    <div>
      <dt className="text-label text-ink-soft">{label}</dt>
      <dd className="num font-medium">{value}</dd>
      {sub && <dd className="num text-label text-ink-soft">{sub}</dd>}
    </div>
  );
}

/** Records the payment as a transaction in the plan's category — one entry, counted once. */
function PaymentForm({ plan, today, onDone }: { plan: InvestmentPlan; today: string; onDone: () => void }) {
  const add = useAddTransactionAnyYear();
  const [date, setDate] = useState(today);
  const [amount, setAmount] = useState(plan.cost_per_installment ? String(plan.cost_per_installment) : '');
  const [units, setUnits] = useState('1');
  const parsed = parseAmount(amount);
  const unitsOk = /^\d{1,3}$/.test(units.trim());
  const valid = parsed !== null && parsed > 0 && date && unitsOk;
  const next = plan.paid + 1;
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (!valid) return;
        const n = Number(units);
        const desc = n === 1 ? `${plan.name} – ${plan.unit} ${next}` : n > 1 ? `${plan.name} – ${plan.unit}s ${next}–${next + n - 1}` : plan.name;
        add.mutate({ type: 'expense', date, amount: parsed!, cat: plan.category, desc, installments: n }, { onSuccess: onDone });
      }}
    >
      <div className="grid grid-cols-3 gap-2">
        <input className="input num" type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Payment date" />
        <input className="input num" inputMode="decimal" placeholder="Amount €" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus aria-label="Payment amount" />
        <input className="input num" inputMode="numeric" value={units} onChange={(e) => setUnits(e.target.value)} aria-label={`${plan.unit}s covered`} title={`${plan.unit}s covered`} />
      </div>
      <p className="text-label text-ink-soft">Date · what left your account in € · how many {plan.unit}s it covers. It is saved as a transaction in “{plan.category}”.</p>
      <ErrorNote error={add.error} />
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-ghost btn-sm" onClick={onDone}>Cancel</button>
        <button type="submit" className="btn-primary btn-sm" disabled={!valid || add.isPending}>Save payment</button>
      </div>
    </form>
  );
}
