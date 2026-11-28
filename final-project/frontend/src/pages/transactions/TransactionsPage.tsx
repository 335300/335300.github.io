import { ArrowRightLeft, Search } from 'lucide-react';
import { useDeferredValue, useEffect, useRef, useState } from 'react';
import { useCategories, useDashboard, useProfiles, useTransactions, useYears } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { MonthNav } from '../../components/ui/MonthGrid';
import { Modal } from '../../components/ui/Modal';
import { Skeleton } from '../../components/ui/States';
import { shortcutLabel, useAddTransactionShortcut } from '../../components/ui/shortcuts';
import { fmtExpense, fmtMoney, fmtSigned, MONTHS } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { TransactionList, TxType } from '../../lib/types';
import { BulkEntryGrid } from './BulkEntryGrid';
import { CategoryManager } from './CategoryManager';
import { ImportModal } from './ImportModal';
import { JointTransactions } from './JointTransactions';
import { PayeeRulesCard } from './PayeeRulesCard';
import { BillSuggestions, RecurringBillsCard } from './RecurringBillsCard';
import { TaxExportModal } from './TaxExportModal';
import { TransactionCalendar } from './TransactionCalendar';
import { TransactionForm } from './TransactionForm';
import { TransactionTable } from './TransactionTable';
import { TransferModal } from './TransferModal';

type View = 'calendar' | 'list';
const VIEW_KEY = 'centwise.transactions-view';

function savedView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === 'calendar' ? 'calendar' : 'list';
  } catch {
    return 'list';
  }
}

const TYPE_CHIPS: [TxType | '', string][] = [['', 'All types'], ['expense', 'Cash out'], ['income', 'Cash in']];

/** The Transactions tab. Joint gets its own plain-English screen. */
export function TransactionsPage({ year }: { year: number }) {
  const isJoint = useProfiles().data?.active === 'joint';
  return isJoint ? <JointTransactions year={year} /> : <PersonalTransactions year={year} />;
}

function PersonalTransactions({ year }: { year: number }) {
  const [type, setType] = useState<TxType | ''>('');
  const [cat, setCat] = useState('');
  const [q, setQ] = useState('');
  const [allMonths, setAllMonths] = useState(false);
  const [view, setViewState] = useState<View>(savedView);
  const month = useUi((s) => s.selectedMonth);
  const setMonth = useUi((s) => s.setMonth);
  const [day, setDay] = useState<string | null>(null);
  const today = useYears().data?.today ?? new Date().toISOString().slice(0, 10);
  const query = useDeferredValue(q);
  const isCalendar = view === 'calendar';
  const showAll = allMonths && !isCalendar;
  const list = useTransactions(year, { type, cat, q: query, month: showAll ? '' : month });
  const dash = useDashboard(year, month);
  const categories = useCategories(year);
  const [importOpen, setImportOpen] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [taxOpen, setTaxOpen] = useState(false);
  const [catsOpen, setCatsOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  const allCats = [...new Set([...(categories.data?.expense ?? []), ...(categories.data?.income ?? [])].map((c) => c.name))].sort();
  const periodLabel = showAll ? `All of ${year}` : `${MONTHS[month]} ${year}`;

  useAddTransactionShortcut(() => setAddOpen(true));
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        search.current?.focus();
        search.current?.select();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const setView = (v: View) => {
    setViewState(v);
    try { localStorage.setItem(VIEW_KEY, v); } catch { /* the choice is only a convenience */ }
  };
  const goMonth = (m: number) => { setMonth(m); setDay(null); };
  const k = dash.data?.kpis;

  // The month's figures from the dashboard; for the whole year, the list's own totals.
  const summary = showAll ? (
    <SummaryStrip label={String(year)} data={list.data} />
  ) : (
    <div className="num flex flex-1 flex-wrap items-center gap-5 text-[13px] text-ink-soft" data-testid="month-summary">
      <span className="font-semibold text-ink">{MONTHS[month]}</span>
      {k && (
        <>
          <span>Cash in <b className="font-semibold text-positive">{fmtMoney(k.cash_in, { sign: true })}</b></span>
          <span>Cash out <b className="font-semibold text-ink">{fmtExpense(k.cash_out)}</b></span>
          <span>Kept <b className={`font-semibold ${k.savings < 0 ? 'text-negative' : 'text-ink'}`}>{fmtSigned(k.savings)}</b></span>
        </>
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-0.5">
          <h1 className="text-page-title text-ink">Transactions</h1>
          <span className="num text-[13px] text-ink-soft" data-testid="transactions-subtitle">
            {periodLabel}{list.data ? ` · ${list.data.count} transaction${list.data.count === 1 ? '' : 's'}` : ''}
          </span>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={() => setCatsOpen(true)}>Categories</button>
          <button type="button" className="btn-secondary" onClick={() => setTransferOpen(true)}>
            <ArrowRightLeft size={14} aria-hidden /> Transfer to Joint
          </button>
          <button type="button" className="btn-secondary" onClick={() => setTaxOpen(true)}>Tax export</button>
          <button type="button" className="btn-secondary" onClick={() => setImportOpen(true)}>Import CSV</button>
          <button type="button" className="btn-primary" onClick={() => setAddOpen(true)}>
            Add transaction <span className="text-label font-medium opacity-85">{shortcutLabel('N')}</span>
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface px-4 py-3 shadow-card">
        <label className="relative flex min-w-[240px] flex-1 items-center">
          <span className="sr-only">Search</span>
          <Search size={14} aria-hidden className="pointer-events-none absolute left-2.5 text-ink-muted" />
          <input ref={search} type="search" className="input pl-8 pr-11" placeholder="Search description or category"
            value={q} onChange={(e) => setQ(e.target.value)} />
          <span aria-hidden className="pointer-events-none absolute right-2 text-label text-ink-muted">{shortcutLabel('F')}</span>
        </label>
        <div role="group" aria-label="Type" className="flex gap-1">
          {TYPE_CHIPS.map(([v, label]) => (
            <button key={label} type="button" aria-pressed={type === v} onClick={() => setType(v)}
              className={`chip h-8 px-3 text-[13px] ${type === v ? 'bg-primary-tint font-semibold text-primary' : 'hover:text-ink'}`}>
              {label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-label text-ink-soft">
          Month
          <select className="input w-36" value={showAll ? '' : month}
            onChange={(e) => {
              if (e.target.value === '') setAllMonths(true);
              else { setAllMonths(false); goMonth(Number(e.target.value)); }
            }}>
            {!isCalendar && <option value="">All months</option>}
            {MONTHS.map((m, i) => <option key={m} value={i}>{m}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-label text-ink-soft">
          Category
          <select className="input w-40" value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="">All categories</option>
            {allCats.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <div role="radiogroup" aria-label="Show transactions as" className="flex gap-0.5 rounded-lg bg-neutral-tint p-[3px]">
          {(['list', 'calendar'] as const).map((v) => (
            <button key={v} type="button" role="radio" aria-checked={view === v} onClick={() => setView(v)}
              className={`h-[26px] rounded-md px-2.5 text-[13px] ${view === v ? 'bg-surface font-semibold text-ink shadow-card' : 'font-medium text-ink-soft hover:text-ink'}`}>
              {v === 'calendar' ? 'Calendar' : 'Table'}
            </button>
          ))}
        </div>
      </div>

      <BulkEntryGrid year={year} />

      <div className="grid grid-cols-[minmax(0,1fr)_340px] items-start gap-4">
        <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card" data-testid="transactions-list">
          {list.isLoading ? <div className="p-5"><Skeleton lines={6} /></div>
            : list.error ? <div className="p-5"><ErrorNote error={list.error} /></div>
            : list.data && (isCalendar ? (
              <>
                <div className="flex min-h-[52px] items-center px-5 py-2.5">{summary}</div>
                <div className="px-5 pb-5">
                  <div className="mb-2 flex justify-center">
                    <MonthNav year={year} month={month}
                      onPrev={month > 0 ? () => goMonth(month - 1) : undefined}
                      onNext={month < 11 ? () => goMonth(month + 1) : undefined} />
                  </div>
                  <TransactionCalendar year={year} month={month} today={today} data={list.data} selected={day} onSelect={setDay} />
                </div>
              </>
            ) : (
              <div className="px-0">
                <TransactionTable key={`${showAll ? 'all' : month}-${type}-${cat}-${query}`} year={year} data={list.data} summary={summary} />
              </div>
            ))}
        </section>
        <div className="flex flex-col gap-4">
          <BillSuggestions />
          <RecurringBillsCard year={year} />
          <PayeeRulesCard year={year} />
        </div>
      </div>

      <ImportModal year={year} open={importOpen} onClose={() => setImportOpen(false)} />
      <TransferModal year={year} open={transferOpen} onClose={() => setTransferOpen(false)} />
      <Modal title="Add a transaction" open={addOpen} onClose={() => setAddOpen(false)}>
        {addOpen && <TransactionForm year={year} idPrefix="modal-tx" initialDate={isCalendar && day ? day : undefined} />}
      </Modal>
      <Modal title="Categories" open={catsOpen} onClose={() => setCatsOpen(false)} width="lg">
        <CategoryManager year={year} />
      </Modal>
      {taxOpen && <TaxExportModal year={year} open onClose={() => setTaxOpen(false)} />}
    </div>
  );
}

/** Whole-year view: the list's own cash in and cash out (from the backend). */
function SummaryStrip({ label, data }: { label: string; data?: TransactionList }) {
  return (
    <div className="num flex flex-1 flex-wrap items-center gap-5 text-[13px] text-ink-soft" data-testid="month-summary">
      <span className="font-semibold text-ink">{label}</span>
      {data && (
        <>
          <span>Cash in <b className="font-semibold text-positive">{fmtMoney(data.total_income, { sign: true })}</b></span>
          <span>Cash out <b className="font-semibold text-ink">{fmtExpense(data.total_expense)}</b></span>
        </>
      )}
    </div>
  );
}
