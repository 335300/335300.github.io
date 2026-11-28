import { CircleX, ClipboardPaste, X } from 'lucide-react';
import { useRef, useState } from 'react';
import { useBulkAdd, useCategories } from '../../api/queries';
import { Card } from '../../components/ui/Card';
import { ErrorNote } from '../../components/ui/Feedback';
import { parseAmount } from '../../lib/format';
import type { TransactionInput, TxType } from '../../lib/types';
import { defaultDate } from './TransactionForm';

interface Row {
  key: number;
  date: string;
  type: TxType;
  amount: string;
  cat: string;
  desc: string;
}

let nextKey = 1;
const blank = (year: number): Row => ({ key: nextKey++, date: defaultDate(year), type: 'expense', amount: '', cat: '', desc: '' });
const START_ROWS = 3;

/** Normalise 31.12.2026 / 31/12/2026 / 2026-12-31 to ISO. */
function parseDate(raw: string): string | null {
  const s = raw.trim();
  let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
  m = s.match(/^(\d{1,2})[./](\d{1,2})[./](\d{4})$/);
  if (m) return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
  return null;
}

/**
 * Turn pasted spreadsheet lines into rows. Expected column order:
 * date, type (optional: expense/income), amount, category, description.
 */
function parsePaste(text: string, year: number): Row[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const cells = line.split(/[\t;]/.test(line) ? /[\t;]/ : ',').map((c) => c.trim());
      const row = blank(year);
      let i = 0;
      const date = parseDate(cells[i] ?? '');
      if (date) {
        row.date = date;
        i++;
      }
      const t = (cells[i] ?? '').toLowerCase();
      if (t === 'income' || t === 'expense') {
        row.type = t;
        i++;
      }
      row.amount = (cells[i++] ?? '').replace(/^[+-]/, '');
      row.cat = cells[i++] ?? '';
      row.desc = cells.slice(i).join(' ');
      return row;
    });
}

interface RowErrors { date?: string; amount?: string; cat?: string }

/** What is wrong with a filled row. Empty rows are simply skipped. */
function check(r: Row, year: number): RowErrors {
  const e: RowErrors = {};
  const n = parseAmount(r.amount);
  if (n === null || n <= 0) e.amount = 'Use a number like 12,50';
  if (!r.cat.trim()) e.cat = 'Choose a category';
  if (!r.date.startsWith(`${year}-`)) e.date = `Use a date in ${year}`;
  return e;
}

const isFilled = (r: Row) => Boolean(r.amount.trim() || r.cat.trim() || r.desc.trim());
const GRID = 'grid grid-cols-[150px_minmax(0,2fr)_minmax(0,1.4fr)_120px_150px_32px] gap-2';

/**
 * Quick entry: several transactions typed in a grid (or pasted from a
 * spreadsheet). Tab moves on, Enter adds a row, ⌘↵ saves. All rows are saved
 * together, or none if one is wrong — nothing is saved before Save.
 */
export function BulkEntryGrid({ year }: { year: number }) {
  const bulk = useBulkAdd(year);
  const categories = useCategories(year);
  const [rows, setRows] = useState<Row[]>(() => Array.from({ length: START_ROWS }, () => blank(year)));
  const [touched, setTouched] = useState<Set<number>>(new Set());
  const [paste, setPaste] = useState('');
  const [showPaste, setShowPaste] = useState(false);
  const [saved, setSaved] = useState<number | null>(null);
  const descRefs = useRef(new Map<number, HTMLInputElement>());

  const filled = rows.filter(isFilled);
  const errors = new Map(filled.map((r) => [r.key, check(r, year)]));
  const badRows = filled.filter((r) => Object.keys(errors.get(r.key)!).length > 0).length;
  const canSave = filled.length > 0 && badRows === 0 && !bulk.isPending;

  const update = (key: number, patch: Partial<Row>) => {
    setSaved(null);
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  };

  const addRowAfter = (key: number) => {
    const fresh = blank(year);
    setRows((rs) => {
      const i = rs.findIndex((r) => r.key === key);
      return i === rs.length - 1 ? [...rs, fresh] : rs;
    });
    const i = rows.findIndex((r) => r.key === key);
    const target = i === rows.length - 1 ? fresh.key : rows[i + 1].key;
    requestAnimationFrame(() => descRefs.current.get(target)?.focus());
  };

  const remove = (key: number) => setRows((rs) => (rs.length > 1 ? rs.filter((r) => r.key !== key) : [blank(year)]));

  const save = () => {
    if (!canSave) {
      setTouched(new Set(filled.map((r) => r.key)));
      return;
    }
    const payload: TransactionInput[] = filled.map((r) => ({
      type: r.type,
      date: r.date,
      amount: parseAmount(r.amount)!,
      cat: r.cat.trim(),
      desc: r.desc.trim(),
    }));
    bulk.mutate(payload, {
      onSuccess: () => {
        setSaved(payload.length);
        setRows(Array.from({ length: START_ROWS }, () => blank(year)));
        setTouched(new Set());
      },
    });
  };

  const onKey = (key: number) => (e: React.KeyboardEvent) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (e.metaKey || e.ctrlKey) save();
    else addRowAfter(key);
  };

  const applyPaste = () => {
    const parsed = parsePaste(paste, year);
    if (parsed.length) setRows([...parsed, blank(year)]);
    setTouched(new Set(parsed.map((r) => r.key)));
    setShowPaste(false);
    setPaste('');
  };

  const fieldErr = (r: Row, field: keyof RowErrors): string | undefined => {
    const e = errors.get(r.key)?.[field];
    if (!e) return undefined;
    // A typed amount that is not a number shows at once; missing fields once the row was left.
    if (field === 'amount' && r.amount.trim()) return e;
    return touched.has(r.key) ? e : undefined;
  };

  return (
    <Card
      title="Quick entry"
      collapseKey="transactions-quick-entry"
      collapseLabel="Quick entry"
      meta="Tab moves on · Enter adds a row · ⌘↵ saves"
      action={
        <button type="button" className="btn-ghost btn-sm" onClick={() => setShowPaste((v) => !v)} aria-expanded={showPaste}>
          <ClipboardPaste size={13} aria-hidden /> Paste from a spreadsheet
        </button>
      }
      testId="quick-entry"
      bodyClassName="!px-0"
    >
      {showPaste && (
        <div className="mx-5 mb-3 rounded-lg border border-line bg-bg p-3">
          <p className="mb-2 text-[13px] text-ink-soft">
            One per line: <strong>date; type; amount; category; description</strong> (type is optional).
            Example: <code className="num">03.10.{year}; 12,40; Groceries; Bakery</code>
          </p>
          <textarea className="input h-28 py-2 font-mono text-[13px]" aria-label="Pasted rows" value={paste} onChange={(e) => setPaste(e.target.value)} />
          <div className="mt-2 flex justify-end">
            <button type="button" className="btn-primary btn-sm" onClick={applyPaste} disabled={!paste.trim()}>Fill the rows</button>
          </div>
        </div>
      )}
      <datalist id="bulk-cats-expense">{categories.data?.expense.map((c) => <option key={c.name} value={c.name} />)}</datalist>
      <datalist id="bulk-cats-income">{categories.data?.income.map((c) => <option key={c.name} value={c.name} />)}</datalist>

      <div className={`${GRID} h-7 items-center px-5 text-label text-ink-soft`} aria-hidden>
        <span>Date</span><span>Description</span><span>Category</span><span>Type</span><span className="text-right">Amount</span><span />
      </div>
      {rows.map((r, i) => {
        const dateErr = fieldErr(r, 'date');
        const catErr = fieldErr(r, 'cat');
        const amtErr = fieldErr(r, 'amount');
        const n = i + 1;
        return (
          <div key={r.key} className={`${GRID} items-start px-5 py-1`} data-testid="quick-entry-row"
            onBlur={(e) => {
              if (isFilled(r) && !e.currentTarget.contains(e.relatedTarget as Node | null)) {
                setTouched((t) => new Set(t).add(r.key));
              }
            }}>
            <div className="flex flex-col gap-1">
              <input type="date" className={`input num ${dateErr ? 'input-error' : ''}`} aria-label={`Date, row ${n}`}
                aria-invalid={!!dateErr} value={r.date} onChange={(e) => update(r.key, { date: e.target.value })} onKeyDown={onKey(r.key)} />
              {dateErr && <InlineError>{dateErr}</InlineError>}
            </div>
            <input className="input" aria-label={`Description, row ${n}`} placeholder="Who did you pay?" value={r.desc}
              ref={(el) => { if (el) descRefs.current.set(r.key, el); else descRefs.current.delete(r.key); }}
              onChange={(e) => update(r.key, { desc: e.target.value })} onKeyDown={onKey(r.key)} />
            <div className="flex flex-col gap-1">
              <input list={`bulk-cats-${r.type}`} className={`input ${catErr ? 'input-error' : ''}`} aria-label={`Category, row ${n}`}
                aria-invalid={!!catErr} placeholder="Choose category" value={r.cat}
                onChange={(e) => update(r.key, { cat: e.target.value })} onKeyDown={onKey(r.key)} />
              {catErr && <InlineError>{catErr}</InlineError>}
            </div>
            <select className="input" aria-label={`Type, row ${n}`} value={r.type}
              onChange={(e) => update(r.key, { type: e.target.value as TxType })} onKeyDown={onKey(r.key)}>
              <option value="expense">Cash out</option>
              <option value="income">Cash in</option>
            </select>
            <div className="flex flex-col gap-1">
              <div className="relative flex items-center">
                <input inputMode="decimal" className={`input num pr-7 text-right ${amtErr ? 'input-error' : ''}`} aria-label={`Amount in euros, row ${n}`}
                  aria-invalid={!!amtErr} placeholder="0,00" value={r.amount}
                  onChange={(e) => update(r.key, { amount: e.target.value })} onKeyDown={onKey(r.key)} />
                <span aria-hidden className="pointer-events-none absolute right-2.5 text-[13px] text-ink-muted">€</span>
              </div>
              {amtErr && <InlineError>{amtErr}</InlineError>}
            </div>
            <button type="button" className="btn-icon h-8 w-8 justify-center" aria-label={`Remove row ${n}`} onClick={() => remove(r.key)}>
              <X size={15} aria-hidden />
            </button>
          </div>
        );
      })}

      <div className="mt-1 flex items-center justify-between gap-3 border-t border-line px-5 pb-1 pt-3">
        <span className="text-[13px] text-ink-soft" role="status">
          {saved !== null
            ? <span className="text-positive">✓ Saved {saved} transaction{saved === 1 ? '' : 's'}</span>
            : badRows > 0
              ? `Fix ${badRows} row${badRows === 1 ? '' : 's'} to save all rows. Nothing is saved until you press Save.`
              : filled.length > 0 ? 'Nothing is saved until you press Save.' : ''}
        </span>
        <div className="flex gap-2">
          <button type="button" className="btn-ghost" onClick={() => setRows((rs) => [...rs, blank(year)])}>+ Add row</button>
          <button type="button" className="btn-primary" onClick={save} disabled={!canSave}>
            Save {filled.length || ''} row{filled.length === 1 ? '' : 's'}
            <span className="text-label font-medium opacity-85">⌘↵</span>
          </button>
        </div>
      </div>
      <div className="px-5"><ErrorNote error={bulk.error} /></div>
    </Card>
  );
}

function InlineError({ children }: { children: string }) {
  return (
    <span className="flex items-center gap-1.5 text-label text-negative">
      <CircleX size={13} strokeWidth={2} aria-hidden className="shrink-0" />
      {children}
    </span>
  );
}
