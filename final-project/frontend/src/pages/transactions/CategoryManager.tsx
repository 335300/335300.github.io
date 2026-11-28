import { Check, Pencil, Plus, Shield, ShieldCheck, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { useAddCategory, useCategories, useDeleteCategory, useUpdateCategory } from '../../api/queries';
import { CategoryDot } from '../../components/ui/CategoryDot';
import { ErrorNote } from '../../components/ui/Feedback';
import type { CategoryKind, CategoryRow, TxType } from '../../lib/types';

export function CategoryManager({ year }: { year: number }) {
  const { data } = useCategories(year);
  const add = useAddCategory(year);
  const update = useUpdateCategory(year);
  const del = useDeleteCategory(year);
  const [kind, setKind] = useState<TxType>('expense');
  const [name, setName] = useState('');
  const [newKind, setNewKind] = useState<CategoryKind>('variable');
  const rows = data?.[kind] ?? [];
  const error = add.error || update.error || del.error;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    add.mutate({ kind, name: name.trim(), category_kind: newKind }, { onSuccess: () => setName('') });
  };

  return (
    <div>
      <div className="mb-3 grid grid-cols-2 gap-1 rounded-lg bg-bg p-0.5">
        {(['expense', 'income'] as const).map((k) => (
          <button key={k} onClick={() => setKind(k)}
            className={`rounded-md py-1 text-xs font-medium ${kind === k ? 'bg-surface text-ink shadow-card' : 'text-ink-soft'}`}>
            {k === 'expense' ? 'Expense categories' : 'Income categories'}
          </button>
        ))}
      </div>
      <ul className="max-h-72 divide-y divide-line/70 overflow-y-auto">
        {rows.map((c) => (
          <CategoryItem
            key={c.name}
            cat={c}
            kind={kind}
            onRename={(newName) => update.mutate({ kind, name: c.name, patch: { name: newName } })}
            onToggle={(ck) => update.mutate({ kind, name: c.name, patch: { category_kind: ck } })}
            onEssential={(essential) => update.mutate({ kind, name: c.name, patch: { essential } })}
            onTax={(tax_relevant) => update.mutate({ kind, name: c.name, patch: { tax_relevant } })}
            onDelete={() => del.mutate({ kind, name: c.name })}
          />
        ))}
        {!rows.length && <li className="py-3 text-xs text-ink-muted">No categories yet.</li>}
      </ul>
      <form onSubmit={submit} className="mt-3 flex gap-2 border-t border-line pt-3">
        <input className="input h-8" placeholder={`New ${kind} category`} value={name} onChange={(e) => setName(e.target.value)} />
        {kind === 'expense' && (
          <select className="input h-8 w-28" value={newKind} onChange={(e) => setNewKind(e.target.value as CategoryKind)} aria-label="Fixed cost, variable cost or investment">
            <option value="variable">Variable</option>
            <option value="fixed">Fixed</option>
            <option value="investment">Investment</option>
          </select>
        )}
        <button className="btn-secondary h-8 px-2" disabled={!name.trim() || add.isPending} aria-label="Add category"><Plus size={14} /></button>
      </form>
      <ErrorNote error={error} />
    </div>
  );
}

const KIND_LABEL: Record<CategoryKind, string> = { fixed: 'Fixed', variable: 'Variable', investment: 'Invest' };
const KIND_ON: Record<CategoryKind, string> = {
  fixed: 'bg-primary-tint text-primary',
  variable: 'bg-secondary-tint text-secondary',
  investment: 'bg-invest-tint text-invest',
};
const KIND_HINT: Record<CategoryKind, string> = {
  fixed: 'A cost that is hard to change short-term: rent, insurance, contracts',
  variable: 'A cost that follows your choices: food, going out, shopping',
  investment: 'Money that builds an asset — cash out, but not an expense',
};

function CategoryItem({ cat, kind, onRename, onToggle, onEssential, onTax, onDelete }: {
  cat: CategoryRow;
  kind: TxType;
  onRename: (name: string) => void;
  onToggle: (kind: CategoryKind) => void;
  onEssential: (essential: boolean) => void;
  onTax: (taxRelevant: boolean) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(cat.name);
  const inUse = cat.transactions > 0;

  if (editing) {
    return (
      <li className="flex items-center gap-1 py-1.5">
        <input className="input h-7 text-xs" value={value} autoFocus onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && value.trim()) { onRename(value.trim()); setEditing(false); }
            if (e.key === 'Escape') setEditing(false);
          }} />
        <button className="btn-ghost btn-sm" aria-label="Save name" onClick={() => { if (value.trim()) onRename(value.trim()); setEditing(false); }}><Check size={13} /></button>
        <button className="btn-ghost btn-sm" aria-label="Cancel" onClick={() => setEditing(false)}><X size={13} /></button>
      </li>
    );
  }
  return (
    <li className="group flex items-center gap-2 py-1.5 text-sm">
      <CategoryDot cat={cat.name} kind={kind === 'expense' ? cat.kind : undefined} income={kind === 'income'} />
      <span className="flex-1 truncate">{cat.name}</span>
      <span className="num text-xs text-ink-muted">{cat.transactions}</span>
      <button
        onClick={() => onTax(!cat.tax_relevant)}
        aria-pressed={cat.tax_relevant}
        aria-label={`${cat.name} is tax-relevant`}
        title={cat.tax_relevant ? 'Tax-relevant — goes into the tax export. Click to unmark.' : 'Mark as tax-relevant (tuition, work equipment…) for the tax export'}
        className={`btn-ghost btn-sm text-[13px] font-semibold ${cat.tax_relevant ? 'text-invest' : 'text-ink-muted opacity-40 group-hover:opacity-100'}`}
      >
        §
      </button>
      {kind === 'expense' && cat.kind !== 'investment' && (
        <button
          onClick={() => onEssential(!cat.essential)}
          aria-pressed={cat.essential}
          aria-label={`${cat.name} is essential`}
          title={cat.essential ? 'Essential — counts for the emergency fund. Click to unmark.' : 'Mark as essential (rent, insurance, groceries…) for the emergency fund'}
          className={`btn-ghost btn-sm ${cat.essential ? 'text-primary' : 'text-ink-muted opacity-40 group-hover:opacity-100'}`}
        >
          {cat.essential ? <ShieldCheck size={13} /> : <Shield size={13} />}
        </button>
      )}
      {kind === 'expense' && (
        <div className="flex rounded-md border border-line text-xs">
          {(['fixed', 'variable', 'investment'] as const).map((k) => (
            <button key={k} onClick={() => k !== cat.kind && onToggle(k)} aria-pressed={cat.kind === k}
              title={KIND_HINT[k]}
              className={`px-1.5 py-0.5 ${cat.kind === k ? KIND_ON[k] : 'text-ink-muted'}`}>
              {KIND_LABEL[k]}
            </button>
          ))}
        </div>
      )}
      <button className="btn-ghost btn-sm opacity-0 group-hover:opacity-100" aria-label={`Rename ${cat.name}`} onClick={() => { setValue(cat.name); setEditing(true); }}><Pencil size={12} /></button>
      <button
        className="btn-ghost btn-sm opacity-0 group-hover:opacity-100 disabled:opacity-0 group-hover:disabled:opacity-30"
        aria-label={`Delete ${cat.name}`}
        disabled={inUse}
        title={inUse ? `Used by ${cat.transactions} transaction(s) — rename it, or move those first.` : 'Delete'}
        onClick={onDelete}
      >
        <Trash2 size={12} />
      </button>
    </li>
  );
}
