import { useState } from 'react';
import { useCategories, useCreateInvestment, useUpdateInvestment } from '../../api/queries';
import { ErrorNote } from '../ui/Feedback';
import { Modal } from '../ui/Modal';
import { parseAmount, parseLocalAmount as parseLocal } from '../../lib/format';
import type { InvestmentPlan } from '../../lib/types';


const wholeNumber = (raw: string): number | null => (/^\d{1,5}$/.test(raw.trim()) ? Number(raw.trim()) : null);

/** Create an investment plan, or edit one when `plan` is given. */
export function InvestmentForm({ open, onClose, plan, year }: { open: boolean; onClose: () => void; plan?: InvestmentPlan; year: number }) {
  const create = useCreateInvestment();
  const update = useUpdateInvestment();
  const categories = useCategories(year);
  const [name, setName] = useState(plan?.name ?? '');
  const [category, setCategory] = useState(plan?.category ?? '');
  const [unit, setUnit] = useState(plan?.unit ?? 'instalment');
  const [currency, setCurrency] = useState(plan?.local_currency ?? '€');
  const [amount, setAmount] = useState(plan ? String(plan.installment_amount) : '');
  const [total, setTotal] = useState(plan ? String(plan.total_installments) : '');
  const [paid, setPaid] = useState(plan ? String(plan.paid_before) : '0');
  const [cost, setCost] = useState(plan?.cost_per_installment ? String(plan.cost_per_installment) : '');
  const [notes, setNotes] = useState(plan?.notes ?? '');
  const [market, setMarket] = useState(plan?.market_value_local ? String(plan.market_value_local) : '');
  const marketN = market.trim() === '' ? 0 : parseLocal(market);

  const amountN = parseLocal(amount);
  const totalN = wholeNumber(total);
  const paidN = wholeNumber(paid);
  const costN = cost.trim() === '' ? 0 : parseAmount(cost);
  const mutation = plan ? update : create;
  const valid =
    name.trim() && category.trim() && unit.trim() && currency.trim() &&
    amountN !== null && amountN > 0 && totalN !== null && totalN > 0 && paidN !== null && costN !== null && costN >= 0
    && marketN !== null && marketN >= 0;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    const body = {
      name: name.trim(), unit: unit.trim(), local_currency: currency.trim(), installment_amount: amountN!,
      total_installments: totalN!, paid_before: paidN!, notes: notes.trim(),
    };
    if (plan) update.mutate({ id: plan.id, patch: { ...body, cost_per_installment: costN!, market_value_local: marketN! } }, { onSuccess: onClose });
    else create.mutate({ ...body, category: category.trim(), cost_per_installment: costN! > 0 ? costN! : null, market_value_local: marketN! > 0 ? marketN! : null }, { onSuccess: onClose });
  };

  return (
    <Modal title={plan ? 'Edit investment plan' : 'New investment plan'} open={open} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="label" htmlFor="inv-name">What are you paying for?</label>
          <input id="inv-name" className="input" placeholder="e.g. Plot of land" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div>
          <label className="label" htmlFor="inv-cat">Category of its payments</label>
          <input id="inv-cat" list="inv-cats" className="input" placeholder="e.g. Investment" value={category}
            onChange={(e) => setCategory(e.target.value)} disabled={!!plan} autoComplete="off" />
          <datalist id="inv-cats">
            {(categories.data?.expense ?? []).map((c) => <option key={c.name} value={c.name} />)}
          </datalist>
          <p className="mt-1.5 text-label text-ink-soft">
            {plan
              ? 'Rename the category in the Transactions tab if you need to.'
              : 'Every payment you record in this category counts toward the plan. It becomes an investment category: cash out, but not an expense.'}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="inv-unit">One payment is called</label>
            <input id="inv-unit" className="input" placeholder="instalment" value={unit} onChange={(e) => setUnit(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="inv-cur">Currency it is fixed in</label>
            <input id="inv-cur" className="input" placeholder="€" value={currency} onChange={(e) => setCurrency(e.target.value)} />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="label" htmlFor="inv-amount">Amount of one</label>
            <input id="inv-amount" inputMode="decimal" className="input num" placeholder="2.170.000" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="inv-total">How many in total</label>
            <input id="inv-total" inputMode="numeric" className="input num" placeholder="130" value={total} onChange={(e) => setTotal(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="inv-paid">Already paid</label>
            <input id="inv-paid" inputMode="numeric" className="input num" value={paid} onChange={(e) => setPaid(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="inv-cost">Roughly what one costs you in € <span className="text-ink-soft">(optional)</span></label>
          <input id="inv-cost" inputMode="decimal" className="input num" placeholder="340" value={cost} onChange={(e) => setCost(e.target.value)} />
          <p className="mt-1.5 text-label text-ink-soft">
            Only used for estimates: what you have built so far and what is still to pay, in euros. “Already paid” is what
            you had paid before recording payments here — later payments add to it.
          </p>
        </div>
        <div>
          <label className="label" htmlFor="inv-market">What it is worth today, in {currency.trim() || 'its currency'} <span className="text-ink-soft">(optional)</span></label>
          <input id="inv-market" inputMode="decimal" className="input num" value={market} onChange={(e) => setMarket(e.target.value)} />
          <p className="mt-1.5 text-label text-ink-soft">Used on the Net worth tab. Without it, the asset counts at its full contract price.</p>
        </div>
        <div>
          <label className="label" htmlFor="inv-notes">Notes <span className="text-ink-soft">(optional)</span></label>
          <input id="inv-notes" className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <ErrorNote error={mutation.error} />
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={!valid || mutation.isPending}>{plan ? 'Save' : 'Create plan'}</button>
        </div>
      </form>
    </Modal>
  );
}
