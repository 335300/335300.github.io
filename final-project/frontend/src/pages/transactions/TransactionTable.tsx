import { Pencil, X } from 'lucide-react';
import { Fragment, useRef, useState, type ReactNode } from 'react';
import { useCategories, useDeleteTransaction, useInvestments, useUpdateTransaction } from '../../api/queries';
import { EmptyState } from '../../components/ui/Card';
import { ConfirmButton } from '../../components/ui/ConfirmButton';
import { ErrorNote } from '../../components/ui/Feedback';
import { Modal } from '../../components/ui/Modal';
import { showUndo } from '../../components/ui/UndoToast';
import { fmtDate, fmtExpense, fmtMoney } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { Transaction, TransactionList, TxType } from '../../lib/types';
import { TransactionForm } from './TransactionForm';
import { chipClass, dotClass, groupByDay, shortDay, useCategoryKinds } from './look';

const PAGE = 50;

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

/**
 * The transactions as a table, grouped by day (each day heading shows the
 * day's cash in and cash out, worked out by the backend). Rows can be
 * selected to change their category or delete them together.
 * Keyboard: ↑↓ move · Space selects · Enter edits · ⌫ deletes (asks first).
 */
export function TransactionTable({ year, data, grouped = true, selectable = true, summary, footer = true, emptyText = 'Try another filter, or add one.' }: {
  year: number;
  data: TransactionList;
  /** Day headings with the day's totals. Off for the calendar's one-day list. */
  grouped?: boolean;
  /** Checkboxes + selection bar. */
  selectable?: boolean;
  /** What the bar above the table shows while nothing is selected (month figures). */
  summary?: ReactNode;
  /** "Shown: x of y", the list totals and the keyboard hints. */
  footer?: boolean;
  emptyText?: string;
}) {
  const del = useDeleteTransaction(year);
  const update = useUpdateTransaction(year);
  const categories = useCategories(year);
  const kinds = useCategoryKinds(year);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [limit, setLimit] = useState(PAGE);
  const [focus, setFocus] = useState(0);
  const [newCat, setNewCat] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [bulkError, setBulkError] = useState<unknown>(null);
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);
  const month = useUi((s) => s.selectedMonth);
  const plans = useInvestments(year, month).data?.plans ?? [];
  const unitOf = (cat: string) => plans.find((p) => p.category === cat)?.unit ?? 'instalment';

  if (!data.count) return <EmptyState title="No transactions match">{emptyText}</EmptyState>;

  // Show whole days: stop at the first day boundary after `limit` rows.
  let cut = Math.min(limit, data.transactions.length);
  while (cut < data.transactions.length && data.transactions[cut].date === data.transactions[cut - 1].date) cut++;
  const shown = data.transactions.slice(0, cut);
  const groups = grouped ? groupByDay(shown) : [['', shown] as [string, Transaction[]]];
  const chosen = data.transactions.filter((t) => selected.has(t.id));
  const chosenTypes = new Set(chosen.map((t) => t.type));
  const oneType: TxType | null = chosenTypes.size === 1 ? [...chosenTypes][0] : null;
  const catChoices = oneType ? (categories.data?.[oneType] ?? []).map((c) => c.name) : [];
  const cols = selectable ? 6 : 5;

  const toggle = (id: number) => setSelected((s) => {
    const next = new Set(s);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const clear = () => { setSelected(new Set()); setNewCat(null); };
  const moveFocus = (i: number) => {
    const j = Math.max(0, Math.min(shown.length - 1, i));
    setFocus(j);
    rowRefs.current[j]?.focus();
  };

  const changeCategory = async (cat: string) => {
    setBusy(true);
    setBulkError(null);
    try {
      for (const t of chosen) {
        await update.mutateAsync({ id: t.id, tx: {
          type: t.type, date: t.date, amount: t.amount, desc: t.desc, cat,
          installments: t.installments, one_off: t.one_off ?? false,
          foreign_amount: t.foreign_amount ?? null, foreign_currency: t.foreign_currency ?? null,
        } });
      }
      showUndo(`${plural(chosen.length, 'transaction')} moved to ${cat}.`);
      clear();
    } catch (e) {
      setBulkError(e);
    } finally {
      setBusy(false);
    }
  };

  const deleteChosen = async () => {
    setBusy(true);
    setBulkError(null);
    try {
      for (const t of chosen) await del.mutateAsync(t.id);
      showUndo(`${plural(chosen.length, 'transaction')} deleted.`);
      clear();
    } catch (e) {
      setBulkError(e);
    } finally {
      setBusy(false);
    }
  };

  const linkedChosen = chosen.some((t) => t.link_id);
  let rowIndex = -1;

  return (
    <>
      {selectable && (
        <div className={`flex min-h-[52px] flex-wrap items-center gap-3 px-5 py-2.5 ${chosen.length ? 'bg-primary-tint' : ''}`}
          data-testid="transactions-bar">
          {chosen.length ? (
            <>
              <span className="text-[13px] font-semibold text-ink">{chosen.length} selected</span>
              <div className="flex-1" />
              {newCat === null ? (
                <button type="button" className="btn-secondary h-7 px-2.5" disabled={!oneType || busy}
                  title={oneType ? undefined : 'Pick only cash in or only cash out rows to change their category'}
                  onClick={() => setNewCat('')}>
                  Change category
                </button>
              ) : (
                <span className="inline-flex items-center gap-2">
                  <select className="input h-7 w-44" aria-label="New category" value={newCat}
                    onChange={(e) => setNewCat(e.target.value)} autoFocus>
                    <option value="">Choose category</option>
                    {catChoices.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <button type="button" className="btn-primary h-7 px-2.5" disabled={!newCat || busy}
                    onClick={() => newCat && changeCategory(newCat)}>Apply</button>
                  <button type="button" className="btn-ghost h-7 px-2" onClick={() => setNewCat(null)}>Cancel</button>
                </span>
              )}
              <ConfirmButton
                label="Delete…"
                question={`Delete ${plural(chosen.length, 'transaction')}?${linkedChosen ? ' Linked ones are also deleted in the other profile.' : ''}`}
                onConfirm={deleteChosen}
                busy={busy}
                testId="delete-selected"
              />
              <button type="button" className="btn-ghost h-7 px-2 text-ink-soft" onClick={clear}>Clear</button>
            </>
          ) : summary}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              {selectable && <th className="w-10"><span className="sr-only">Select</span></th>}
              <th className="w-20">Date</th>
              <th>Description</th>
              <th>Category</th>
              <th className="cell-num w-36">Amount</th>
              <th className="w-20"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {groups.map(([day, rows]) => (
              <Fragment key={day || 'all'}>
                {grouped && <DayRow day={day} totals={data.days[day]} cols={cols} />}
                {rows.map((t) => {
                  rowIndex++;
                  const i = rowIndex;
                  const isSel = selected.has(t.id);
                  const kind = kinds.get(t.cat);
                  const label = t.desc || t.payee || t.cat;
                  return (
                    <tr key={t.id}
                      ref={(el) => { rowRefs.current[i] = el; }}
                      tabIndex={i === focus ? 0 : -1}
                      aria-selected={selectable ? isSel : undefined}
                      onFocus={(e) => { if (e.target === e.currentTarget) setFocus(i); }}
                      onKeyDown={(e) => {
                        if (e.target !== e.currentTarget) return;
                        if (e.key === 'ArrowDown') { e.preventDefault(); moveFocus(i + 1); }
                        else if (e.key === 'ArrowUp') { e.preventDefault(); moveFocus(i - 1); }
                        else if (e.key === ' ' && selectable) { e.preventDefault(); toggle(t.id); }
                        else if (e.key === 'Enter') { e.preventDefault(); setEditing(t); }
                        else if (e.key === 'Backspace' || e.key === 'Delete') { e.preventDefault(); setConfirmId(t.id); }
                      }}>
                      {selectable && (
                        <td>
                          <input type="checkbox" className="h-4 w-4 cursor-pointer accent-[rgb(var(--c-primary))]"
                            checked={isSel} onChange={() => toggle(t.id)} aria-label={`Select ${label}`} />
                        </td>
                      )}
                      <td className="num text-ink-soft">{fmtDate(t.date, { short: true })}</td>
                      <td className="max-w-[280px]">
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="truncate" title={t.payee && t.payee !== label ? t.payee : undefined}>
                            {label || <span className="text-ink-muted">—</span>}
                          </span>
                          {t.one_off && <Tag className="border-warning text-warning-ink">one-off</Tag>}
                          {t.link_id && <Tag title="Transfer between Personal and Joint">linked · Personal ↔ Joint</Tag>}
                        </span>
                      </td>
                      <td>
                        <span className="inline-flex items-center gap-1.5">
                          <span className={chipClass(kind)}>
                            <span aria-hidden className={`h-2 w-2 rounded-full ${dotClass(t.cat, kind, t.type === 'income')}`} />
                            {t.cat}
                          </span>
                          {!!t.installments && (
                            <span className="chip num bg-invest-tint text-invest">
                              {t.installments} {unitOf(t.cat)}{t.installments === 1 ? '' : 's'}
                            </span>
                          )}
                        </span>
                      </td>
                      <td className={`cell-num font-medium ${t.type === 'income' ? 'text-positive' : 'text-ink'}`}>
                        {t.type === 'income' ? fmtMoney(t.amount, { sign: true }) : fmtExpense(t.amount)}
                      </td>
                      <td className="text-right">
                        {confirmId === t.id ? (
                          <RowConfirm linked={!!t.link_id} onKeep={() => { setConfirmId(null); rowRefs.current[i]?.focus(); }}
                            onDelete={() => del.mutate(t.id, { onSuccess: () => { setConfirmId(null); showUndo('Transaction deleted.'); } })} />
                        ) : (
                          <span className="inline-flex gap-0.5">
                            <button type="button" className="btn-icon h-7" aria-label="Edit" title="Edit" onClick={() => setEditing(t)}>
                              <Pencil size={14} aria-hidden />
                            </button>
                            <button type="button" className="btn-icon h-7 hover:bg-negative-tint hover:text-negative" aria-label="Delete" title="Delete"
                              onClick={() => setConfirmId(t.id)}>
                              <X size={15} aria-hidden />
                            </button>
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </Fragment>
            ))}
          </tbody>
          {footer && (
            <tfoot>
              <tr>
                <td colSpan={selectable ? 3 : 2} className="num">Shown: {shown.length} of {data.count}</td>
                <td colSpan={2} className="num text-right font-medium text-ink-soft">
                  Cash in <span className="text-positive">{fmtMoney(data.total_income, { sign: true })}</span>
                  <span className="mx-2 text-ink-muted">·</span>
                  Cash out <span className="text-ink">{fmtExpense(data.total_expense)}</span>
                </td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {footer && (
        <div className="flex items-center justify-between gap-3 px-5 pb-3.5 pt-2.5 text-[13px] text-ink-soft">
          <span>↑↓ move · Space selects · Enter edits · ⌫ deletes (asks first)</span>
          {shown.length < data.count && (
            <button type="button" className="font-medium text-primary hover:underline" onClick={() => setLimit((n) => n + PAGE)}>
              Show {Math.min(PAGE, data.count - shown.length)} more
            </button>
          )}
        </div>
      )}
      <ErrorNote error={del.error || bulkError} />
      <Modal title="Edit transaction" open={editing !== null} onClose={() => setEditing(null)}>
        {editing && <TransactionForm key={editing.id} year={year} editing={editing} idPrefix="edit-tx" onDone={() => setEditing(null)} />}
      </Modal>
    </>
  );
}

/** Day heading: "Thu 19.11." and the day's cash in / cash out from the backend. */
function DayRow({ day, totals, cols }: { day: string; totals?: { income: number; expense: number }; cols: number }) {
  return (
    <tr>
      <td colSpan={cols} className="!h-7 bg-bg !pl-[60px] text-label text-ink-soft">
        <span className="flex items-center justify-between gap-4">
          <span>{shortDay(day)}</span>
          {totals && (
            <span className="num flex gap-3">
              {totals.income > 0 && <span className="text-positive">{fmtMoney(totals.income, { sign: true })}</span>}
              {totals.expense > 0 && <span>{fmtExpense(totals.expense)}</span>}
            </span>
          )}
        </span>
      </td>
    </tr>
  );
}

function Tag({ children, className = 'border-line-strong text-ink-soft', title }: { children: ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={`shrink-0 whitespace-nowrap rounded-input border px-1.5 text-label leading-[18px] ${className}`}>
      {children}
    </span>
  );
}

function RowConfirm({ linked, onKeep, onDelete }: { linked: boolean; onKeep: () => void; onDelete: () => void }) {
  return (
    <span role="group" aria-label="Delete this transaction?" className="inline-flex items-center gap-1.5 rounded-lg bg-negative-tint py-0.5 pl-2 pr-0.5"
      onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); onKeep(); } }}>
      <span className="whitespace-nowrap text-label text-ink">{linked ? 'Also deletes it in the other profile.' : 'Delete?'}</span>
      <button type="button" className="btn-secondary btn-sm" autoFocus onClick={onKeep}>Keep</button>
      <button type="button" className="btn-danger-solid btn-sm" onClick={onDelete}>Delete</button>
    </span>
  );
}
