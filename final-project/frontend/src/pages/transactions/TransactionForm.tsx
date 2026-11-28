import { useEffect, useState } from 'react';
import { useAddTransaction, useCategories, useInvestments, useUpdateTransaction } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { isoDate, parseAmount, parseLocalAmount } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { Transaction, TxType } from '../../lib/types';

export function defaultDate(year: number): string {
  const today = new Date();
  return today.getFullYear() === year ? isoDate(today) : `${year}-01-01`;
}

/**
 * Add one transaction, or edit an existing one when `editing` is given.
 * `initialDate` pre-fills the date of a new one (a day picked in the calendar);
 * `idPrefix` keeps field ids unique when the form is on screen more than once.
 */
export function TransactionForm({ year, editing, onDone, initialDate, idPrefix = 'tx' }: {
  year: number;
  editing?: Transaction;
  onDone?: () => void;
  initialDate?: string;
  idPrefix?: string;
}) {
  const add = useAddTransaction(year);
  const update = useUpdateTransaction(year);
  const categories = useCategories(year);
  const [type, setType] = useState<TxType>(editing?.type ?? 'expense');
  const [date, setDate] = useState(editing?.date ?? initialDate ?? defaultDate(year));
  const [amount, setAmount] = useState(editing ? String(editing.amount) : '');
  const [cat, setCat] = useState(editing?.cat ?? '');
  const [desc, setDesc] = useState(editing?.desc ?? '');
  // A payment into an investment plan's category says how many instalments it covers.
  const [units, setUnits] = useState(editing ? String(editing.installments ?? 0) : '1');
  const [oneOff, setOneOff] = useState(editing?.one_off ?? false);
  const [foreign, setForeign] = useState(editing?.foreign_amount ? String(editing.foreign_amount) : '');
  const [saved, setSaved] = useState(false);
  const month = useUi((s) => s.selectedMonth);
  const plans = useInvestments(year, month).data?.plans ?? [];

  useEffect(() => {
    if (!saved) return;
    const t = setTimeout(() => setSaved(false), 1800);
    return () => clearTimeout(t);
  }, [saved]);

  const parsed = parseAmount(amount);
  const amountInvalid = amount.trim() !== '' && (parsed === null || parsed <= 0);
  const options = categories.data?.[type] ?? [];
  const mutation = editing ? update : add;
  const isNewCategory = cat.trim() !== '' && !options.some((c) => c.name === cat.trim());
  const plan = type === 'expense' ? plans.find((p) => p.category === cat.trim()) : undefined;
  const unitsInvalid = !!plan && !/^\d{1,3}$/.test(units.trim());
  // A payment in another currency (the land in guaraníes) can record what arrived there.
  const foreignCurrency = plan && plan.local_currency.trim() !== '€' ? 'PYG' : null;
  const foreignN = foreign.trim() ? parseLocalAmount(foreign) : null;
  const foreignInvalid = foreign.trim() !== '' && (foreignN === null || foreignN <= 0);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (parsed === null || parsed <= 0 || !cat.trim() || unitsInvalid || foreignInvalid) return;
    const tx = {
      type, date, amount: parsed, cat: cat.trim(), desc: desc.trim(), installments: plan ? Number(units) : null, one_off: oneOff,
      foreign_amount: foreignCurrency && foreignN ? foreignN : null, foreign_currency: foreignCurrency && foreignN ? foreignCurrency : null,
    } as const;
    if (editing) {
      update.mutate({ id: editing.id, tx }, { onSuccess: () => onDone?.() });
    } else {
      add.mutate(tx, {
        onSuccess: () => {
          setAmount('');
          setDesc('');
          setOneOff(false);
          setForeign('');
          setSaved(true);
          onDone?.();
        },
      });
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid grid-cols-2 gap-1 rounded-lg bg-bg p-0.5" role="radiogroup" aria-label="Type">
        {(['expense', 'income'] as const).map((t) => (
          <button
            type="button"
            key={t}
            role="radio"
            aria-checked={type === t}
            onClick={() => setType(t)}
            className={`rounded-md py-1.5 text-sm font-medium ${type === t ? 'bg-surface text-ink shadow-card' : 'text-ink-soft'}`}
          >
            {t === 'expense' ? '− Expense' : '+ Income'}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor={`${idPrefix}-date`}>Date</label>
          <input id={`${idPrefix}-date`} type="date" className="input num" value={date} min={`${year}-01-01`} max={`${year}-12-31`}
            onChange={(e) => setDate(e.target.value)} required />
        </div>
        <div>
          <label className="label" htmlFor={`${idPrefix}-amount`}>Amount (€)</label>
          <input id={`${idPrefix}-amount`} inputMode="decimal" className="input num" placeholder="0,00" value={amount}
            onChange={(e) => setAmount(e.target.value)} required aria-invalid={amountInvalid} />
        </div>
      </div>
      <div>
        <label className="label" htmlFor={`${idPrefix}-cat`}>Category</label>
        <input id={`${idPrefix}-cat`} list={`${idPrefix}-cats-${type}`} className="input" placeholder={type === 'expense' ? 'e.g. Groceries' : 'e.g. Salary'}
          value={cat} onChange={(e) => setCat(e.target.value)} required autoComplete="off" />
        <datalist id={`${idPrefix}-cats-${type}`}>
          {options.map((c) => (
            <option key={c.name} value={c.name} />
          ))}
        </datalist>
        {isNewCategory && <p className="mt-1 text-xs text-ink-muted">“{cat.trim()}” is new — it will be added as a variable {type} category.</p>}
      </div>
      {plan && (
        <div>
          <label className="label" htmlFor={`${idPrefix}-units`}>{plan.unit[0].toUpperCase() + plan.unit.slice(1)}s covered</label>
          <input id={`${idPrefix}-units`} inputMode="numeric" className="input num" value={units} onChange={(e) => setUnits(e.target.value)}
            aria-invalid={unitsInvalid} />
          <p className="mt-1 text-xs text-ink-muted">
            Counts toward “{plan.name}” ({plan.paid} of {plan.total_installments} paid). Use 0 for a payment that is not a {plan.unit}.
          </p>
        </div>
      )}
      {foreignCurrency && plan && (
        <div>
          <label className="label" htmlFor={`${idPrefix}-foreign`}>{plan.local_currency} received <span className="font-normal text-ink-muted">(optional)</span></label>
          <input id={`${idPrefix}-foreign`} inputMode="decimal" className="input num" placeholder="2.170.000" value={foreign}
            onChange={(e) => setForeign(e.target.value)} aria-invalid={foreignInvalid} />
        </div>
      )}
      <div>
        <label className="label" htmlFor={`${idPrefix}-desc`}>Description <span className="font-normal text-ink-muted">(optional)</span></label>
        <input id={`${idPrefix}-desc`} className="input" placeholder="What was it?" value={desc} onChange={(e) => setDesc(e.target.value)} />
      </div>
      <label className="flex items-start gap-2 text-sm" title="A wedding, a big repair, a double salary: left out of every “usual” figure">
        <input id={`${idPrefix}-oneoff`} type="checkbox" className="mt-0.5" checked={oneOff} onChange={(e) => setOneOff(e.target.checked)} />
        <span>One-off</span>
      </label>
      {editing?.link_id && (
        <p className="text-xs text-ink-muted">Part of a Transfer to Joint: a new date or amount also changes the matching record in the other profile.</p>
      )}
      {amountInvalid && <p className="text-xs text-negative">Enter an amount above zero, e.g. 12,50</p>}
      <ErrorNote error={mutation.error} />
      <div className="flex items-center gap-3">
        <button type="submit" className="btn-primary flex-1" disabled={mutation.isPending || amountInvalid || unitsInvalid || foreignInvalid}>
          {editing ? 'Save changes' : `Add ${type}`}
        </button>
        {saved && <span className="text-xs font-medium text-secondary" role="status">✓ Added</span>}
      </div>
    </form>
  );
}
