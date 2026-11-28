import { ChevronDown, Pencil, Search, Trash2 } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { useDashboard, useDeleteTransaction, useTransactions, useYears } from '../../api/queries';
import { EmptyState } from '../../components/ui/Card';
import { ErrorNote } from '../../components/ui/Feedback';
import { KpiTile, type KpiComparison } from '../../components/ui/KpiTile';
import { Modal } from '../../components/ui/Modal';
import { Skeleton } from '../../components/ui/States';
import { useAddTransactionShortcut } from '../../components/ui/shortcuts';
import { fmtExpense, fmtMoney, MONTHS } from '../../lib/format';
import { useStoredFlag } from '../../lib/useCollapsed';
import { useUi } from '../../lib/store';
import type { Dashboard, Transaction, TxType } from '../../lib/types';
import { BulkEntryGrid } from './BulkEntryGrid';
import { CategoryManager } from './CategoryManager';
import { ImportModal } from './ImportModal';
import { PayeeRulesCard } from './PayeeRulesCard';
import { RecurringBillsCard } from './RecurringBillsCard';
import { TaxExportModal } from './TaxExportModal';
import { TransactionForm } from './TransactionForm';
import { daysInMonth, dotClass, groupByDay, longDay, useCategoryKinds } from './look';

/** Who a row came from or how it was paid — plain words for Isa. */
function who(t: Transaction): string {
  if (t.type === 'income') return t.cat.startsWith('From ') ? t.cat : 'Money in';
  return 'Paid from our account';
}

/** "About 40 € less than usual." — words from the backend's comparison. */
function usualNote(d: Dashboard | undefined): KpiComparison | undefined {
  const c = d?.vs_usual?.cash_out;
  if (!c) return undefined;
  if (c.direction === null || c.diff === null) return { direction: 'none', text: 'Nothing to compare with yet.' };
  if (c.direction === 'same') return { direction: 'same', text: 'About the same as usual.' };
  // The direction word carries the sign, so the amount is shown without one.
  const amount = fmtMoney(c.diff, { round: true }).replace('\u2212', '');
  return c.direction === 'down'
    ? { direction: 'down', text: `About ${amount} less than usual.`, tone: 'good' }
    : { direction: 'up', text: `About ${amount} more than usual.`, tone: 'bad' };
}

/**
 * Joint Transactions (for Isa): everything paid from the shared account in
 * the month, in plain English. Figures come from the dashboard and the
 * transaction list the backend sends.
 */
export function JointTransactions({ year }: { year: number }) {
  const month = useUi((s) => s.selectedMonth);
  const [q, setQ] = useState('');
  const [type, setType] = useState<TxType | ''>('');
  const query = useDeferredValue(q);
  const list = useTransactions(year, { month, type, q: query, cat: '' });
  const incoming = useTransactions(year, { month, type: 'income', q: '', cat: '' });
  const dash = useDashboard(year, month);
  const years = useYears().data;
  const kinds = useCategoryKinds(year);
  const del = useDeleteTransaction(year);
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [toolsOpen, toggleTools] = useStoredFlag('pc-joint-tx-tools-open', false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [catsOpen, setCatsOpen] = useState(false);
  const [taxOpen, setTaxOpen] = useState(false);
  useAddTransactionShortcut(() => setAddOpen(true));

  const monthName = MONTHS[month];
  const isNow = years?.current_year === year && years?.current_month === month;
  const lastDay = isNow && years ? Number(years.today.slice(8, 10)) : daysInMonth(year, month);
  const k = dash.data?.kpis;
  const ins = incoming.data?.transactions ?? [];
  const inNote = !incoming.data ? undefined
    : ins.length === 0 ? 'Nothing has come in yet.'
    : ins.length <= 3 ? ins.map((t) => `${t.cat.startsWith('From ') ? t.cat : t.desc || t.cat} ${fmtMoney(t.amount, { round: true })}`).join(' · ')
    : `${ins.length} payments came in.`;
  const up = dash.data?.upcoming;
  const leftNote = !up ? undefined
    : !isNow ? `At the end of ${monthName}.`
    : up.items.length ? `${up.items.length} bill${up.items.length === 1 ? '' : 's'} still to come in the next ${up.days} days: ${fmtMoney(up.total)}.`
    : `No bills due in the next ${up.days} days.`;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-[15px] text-ink-soft">Our shared account · {monthName}</span>
          <h1 className="text-[32px] font-semibold leading-10 text-ink">Everything we paid together</h1>
        </div>
        <button type="button" className="btn-primary h-11 px-[18px] text-[15px]" onClick={() => setAddOpen(true)}>Add a payment</button>
      </div>

      <div className="grid grid-cols-3 gap-5" data-testid="joint-tx-tiles">
        <KpiTile variant="hero" label="Money in" value={k ? fmtMoney(k.cash_in, { round: true, sign: true }) : '—'} tone="positive" meta={inNote} />
        <KpiTile variant="hero" label="Money out" value={k ? fmtExpense(k.cash_out, { round: true }) : '—'} comparison={usualNote(dash.data)} />
        <KpiTile variant="hero" label="Left in the account" value={k ? fmtMoney(k.current_balance, { round: true }) : '—'}
          tone={k?.negative_balance ? 'negative' : 'neutral'} alert={k?.negative_balance} meta={leftNote} />
      </div>

      <div className="flex items-center gap-3">
        <label className="relative flex flex-1 items-center">
          <span className="sr-only">Search</span>
          <Search size={16} aria-hidden className="pointer-events-none absolute left-3.5 text-ink-muted" />
          <input type="search" className="input h-11 pl-10 text-[15px]" placeholder="Search, for example “groceries”"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <label className="flex items-center gap-2 text-[15px] text-ink-soft">
          Show
          <select className="input h-11 w-48 text-[15px]" value={type} onChange={(e) => setType(e.target.value as TxType | '')}>
            <option value="">Everything</option>
            <option value="income">Only money in</option>
            <option value="expense">Only money out</option>
          </select>
        </label>
      </div>

      <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card" data-testid="joint-tx-list">
        {list.isLoading ? <div className="p-6"><Skeleton lines={5} /></div>
          : list.error ? <div className="p-6"><ErrorNote error={list.error} /></div>
          : !list.data?.count ? (
            <div className="px-6">
              <EmptyState title="No transactions match"
                action={<button type="button" className="btn-primary" onClick={() => setAddOpen(true)}>Add a payment</button>}>
                {q || type ? 'Try another search, or show everything.' : `Nothing paid together in ${monthName} yet.`}
              </EmptyState>
            </div>
          ) : (
            <>
              {groupByDay(list.data.transactions).map(([day, rows]) => (
                <div key={day}>
                  <div className="flex h-10 items-center border-b border-line bg-bg px-6 text-[14px] font-semibold text-ink-soft">{longDay(day)}</div>
                  {rows.map((t) => (
                    <div key={t.id} className="group grid min-h-14 grid-cols-[minmax(0,2fr)_minmax(0,1.2fr)_180px_88px] items-center gap-4 border-b border-line px-6 py-2 text-[15px] hover:bg-neutral-tint">
                      <span className="flex min-w-0 flex-col">
                        <span className="truncate font-medium text-ink">{t.desc || t.cat}</span>
                        <span className="text-[14px] text-ink-soft">{who(t)}</span>
                      </span>
                      <span>
                        <span className="chip h-7 px-2.5 text-[14px]">
                          <span aria-hidden className={`h-2 w-2 rounded-full ${dotClass(t.cat, kinds.get(t.cat), t.type === 'income')}`} />
                          {t.type === 'income' ? 'Money in' : t.cat}
                        </span>
                      </span>
                      <span className={`num text-right font-medium ${t.type === 'income' ? 'text-positive' : 'text-ink'}`}>
                        {t.type === 'income' ? fmtMoney(t.amount, { sign: true }) : fmtExpense(t.amount)}
                      </span>
                      <span className="flex justify-end gap-1">
                        {confirmId === t.id ? (
                          <span role="group" aria-label="Delete this payment?" className="col-span-full flex items-center gap-1.5 rounded-lg bg-negative-tint py-0.5 pl-2 pr-0.5">
                            <span className="whitespace-nowrap text-[14px]">{t.link_id ? 'Also deletes it in Personal.' : 'Delete?'}</span>
                            <button type="button" className="btn-secondary btn-sm" autoFocus onClick={() => setConfirmId(null)}>Keep</button>
                            <button type="button" className="btn-danger-solid btn-sm" onClick={() => del.mutate(t.id, { onSuccess: () => setConfirmId(null) })}>Delete</button>
                          </span>
                        ) : (
                          <>
                            <button type="button" className="btn-icon h-8" aria-label="Edit" title="Change this payment" onClick={() => setEditing(t)}><Pencil size={15} aria-hidden /></button>
                            <button type="button" className="btn-icon h-8" aria-label="Delete" title="Delete this payment" onClick={() => setConfirmId(t.id)}><Trash2 size={15} aria-hidden /></button>
                          </>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              ))}
              <p className="px-6 py-4 text-[15px] text-ink-soft">
                That’s everything from 1 to {lastDay} {monthName}.
                <span className="sr-only"> {list.data.count} transactions.</span>
              </p>
            </>
          )}
        <ErrorNote error={del.error} />
      </section>

      <div>
        <button type="button" className="btn-ghost text-[15px]" aria-expanded={toolsOpen} onClick={toggleTools}>
          More tools <ChevronDown size={16} aria-hidden className={toolsOpen ? 'rotate-180' : ''} />
        </button>
        {toolsOpen && (
          <div className="mt-3 flex flex-col gap-5" data-testid="joint-tx-tools">
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary" aria-pressed={bulkOpen} onClick={() => setBulkOpen((v) => !v)}>Add several at once</button>
              <button type="button" className="btn-secondary" onClick={() => setImportOpen(true)}>Import a bank file</button>
              <button type="button" className="btn-secondary" onClick={() => setCatsOpen(true)}>Categories</button>
              <button type="button" className="btn-secondary" onClick={() => setTaxOpen(true)}>Tax export</button>
            </div>
            {bulkOpen && <BulkEntryGrid year={year} />}
            <div className="grid grid-cols-2 items-start gap-5">
              <RecurringBillsCard year={year} />
              <PayeeRulesCard year={year} />
            </div>
          </div>
        )}
      </div>

      <Modal title="Add a payment" open={addOpen} onClose={() => setAddOpen(false)}>
        {addOpen && <TransactionForm year={year} idPrefix="modal-tx" />}
      </Modal>
      <Modal title="Change this payment" open={editing !== null} onClose={() => setEditing(null)}>
        {editing && <TransactionForm key={editing.id} year={year} editing={editing} idPrefix="edit-tx" onDone={() => setEditing(null)} />}
      </Modal>
      <Modal title="Categories" open={catsOpen} onClose={() => setCatsOpen(false)} width="lg">
        <CategoryManager year={year} />
      </Modal>
      <ImportModal year={year} open={importOpen} onClose={() => setImportOpen(false)} />
      {taxOpen && <TaxExportModal year={year} open onClose={() => setTaxOpen(false)} />}
    </div>
  );
}
