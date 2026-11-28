import { Lightbulb, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useAddRule, useCategories, useDeleteRule, useDismissSuggestion, useRules } from '../../api/queries';
import { Card } from '../../components/ui/Card';
import { ErrorNote } from '../../components/ui/Feedback';
import type { PayeeRule, TxType } from '../../lib/types';
import { dotClass, useCategoryKinds } from './look';

const TYPE_WORD: Record<string, string> = { expense: 'expenses', income: 'income' };

/**
 * Payee rules: "if the payee or purpose contains X, use category Y" — applied
 * when a statement file is imported. Suggestions come from the backend after the
 * same payee got the same category twice.
 */
export function PayeeRulesCard({ year }: { year: number }) {
  const { data } = useRules();
  const categories = useCategories(year);
  const kinds = useCategoryKinds(year);
  const add = useAddRule();
  const del = useDeleteRule();
  const dismiss = useDismissSuggestion();
  const [adding, setAdding] = useState(false);
  const [contains, setContains] = useState('');
  const [category, setCategory] = useState('');
  const [txType, setTxType] = useState<TxType | ''>('');
  const [late, setLate] = useState(false);
  const allCats = [...new Set([...(categories.data?.expense ?? []), ...(categories.data?.income ?? [])].map((c) => c.name))].sort();
  const valid = contains.trim() && category.trim();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    add.mutate(
      { contains: contains.trim(), category: category.trim(), tx_type: txType || null, next_month_if_late: late },
      { onSuccess: () => { setContains(''); setCategory(''); setTxType(''); setLate(false); setAdding(false); } },
    );
  };

  return (
    <Card title="Payee rules" meta="used on import" testId="payee-rules" bodyClassName="!pt-1">
      {data?.suggestions.map((s) => (
        <div key={`${s.contains}-${s.tx_type}`} className="mb-2 rounded-lg border border-line bg-bg px-3 py-2 text-[13px]">
          <p className="flex items-start gap-1.5 text-ink-soft">
            <Lightbulb size={14} aria-hidden className="mt-0.5 shrink-0 text-info" />
            <span>You gave “{s.example_payee}” the category <b className="font-semibold text-ink">{s.category}</b> {s.count} times. Add a rule?</span>
          </p>
          <div className="mt-1.5 flex flex-wrap gap-2">
            <button type="button" className="btn-secondary btn-sm" onClick={() => add.mutate({ contains: s.contains, category: s.category, tx_type: s.tx_type, next_month_if_late: false })}>
              Add rule “{s.contains}” → {s.category}
            </button>
            <button type="button" className="btn-ghost btn-sm text-ink-soft" onClick={() => dismiss.mutate(s.contains)}>No thanks</button>
          </div>
        </div>
      ))}

      <ul>
        {data?.rules.map((r) => <RuleItem key={r.id} rule={r} dot={dotClass(r.category, kinds.get(r.category), r.tx_type === 'income')} onDelete={() => del.mutate(r.id)} />)}
        {data && !data.rules.length && <li className="py-2 text-[13px] text-ink-soft">No rules yet. Example: “REWE” → Groceries.</li>}
      </ul>

      {adding ? (
        <form onSubmit={submit} className="mt-3 space-y-2">
          <div className="flex gap-2">
            <input className="input" placeholder="Payee contains…" value={contains} onChange={(e) => setContains(e.target.value)} aria-label="Rule text" autoFocus />
            <input className="input" placeholder="Category" list="rule-cats" value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Rule category" />
            <datalist id="rule-cats">{allCats.map((c) => <option key={c} value={c} />)}</datalist>
          </div>
          <select className="input" value={txType} onChange={(e) => setTxType(e.target.value as TxType | '')} aria-label="Rule applies to">
            <option value="">Any type</option>
            <option value="expense">Expenses</option>
            <option value="income">Income</option>
          </select>
          <label className="flex items-start gap-2 text-[13px] text-ink-soft" title="For salary and month-end rent, which pay for the coming month">
            <input type="checkbox" className="mt-0.5" checked={late} onChange={(e) => setLate(e.target.checked)} />
            Paid on the 25th or later → book on the 1st of next month
          </label>
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-ghost text-ink-soft" onClick={() => setAdding(false)}>Cancel</button>
            <button className="btn-primary" disabled={!valid || add.isPending} aria-label="Add rule">Add rule</button>
          </div>
        </form>
      ) : (
        <button type="button" className="btn-ghost -ml-3 mt-2" onClick={() => setAdding(true)}>+ Add rule</button>
      )}
      <ErrorNote error={add.error || del.error || dismiss.error} />
    </Card>
  );
}

function RuleItem({ rule, dot, onDelete }: { rule: PayeeRule; dot: string; onDelete: () => void }) {
  const extra = [rule.tx_type && `only ${TYPE_WORD[rule.tx_type]}`, rule.next_month_if_late && 'late payments booked next month'].filter(Boolean).join(' · ');
  return (
    <li className="group grid min-h-9 grid-cols-[minmax(0,1fr)_16px_minmax(0,1fr)_auto] items-center gap-2 border-b border-line py-1 text-[13px]">
      <span className="truncate font-mono text-label text-ink" title={rule.contains}>{rule.contains}</span>
      <span aria-hidden className="text-ink-muted">→</span>
      <span className="flex min-w-0 flex-col">
        <span className="inline-flex items-center gap-1.5 text-label text-ink-soft">
          <span aria-hidden className={`h-2 w-2 shrink-0 rounded-full ${dot}`} />
          <span className="truncate">{rule.category}</span>
        </span>
        {extra && <span className="text-label text-ink-muted">{extra}</span>}
      </span>
      <button type="button" className="btn-icon h-7 opacity-0 focus:opacity-100 group-hover:opacity-100" aria-label={`Delete rule ${rule.contains}`} onClick={onDelete}>
        <Trash2 size={13} aria-hidden />
      </button>
    </li>
  );
}
