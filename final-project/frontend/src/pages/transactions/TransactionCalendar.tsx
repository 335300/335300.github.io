import { Plus, X } from 'lucide-react';
import { useState } from 'react';
import { MonthGrid } from '../../components/ui/MonthGrid';
import { fmtDate, fmtExpense, fmtMoney } from '../../lib/format';
import type { TransactionList } from '../../lib/types';
import { TransactionForm } from './TransactionForm';
import { TransactionTable } from './TransactionTable';

const SHOWN_PER_DAY = 3;

/**
 * The year's transactions as a month calendar: each day shows its first few
 * movements and, when there are several, the day's totals (from the backend).
 * Clicking a day opens its movements below the calendar to edit or delete, and
 * "Add on this day" (or the "+" on a day) adds one with that date.
 */
export function TransactionCalendar({ year, month, today, data, selected, onSelect }: {
  year: number;
  month: number;
  today: string;
  data: TransactionList;
  selected: string | null;
  onSelect: (iso: string | null) => void;
}) {
  const byDay = new Map<string, TransactionList['transactions']>();
  for (const t of [...data.transactions].reverse()) {
    byDay.set(t.date, [...(byDay.get(t.date) ?? []), t]);
  }
  const [addingFor, setAddingFor] = useState<string | null>(null);
  const adding = selected !== null && addingFor === selected;
  const dayList = selected ? byDay.get(selected) ?? [] : [];
  const dayTotals = selected ? data.days[selected] ?? { income: 0, expense: 0 } : null;
  const startAdding = (iso: string) => { onSelect(iso); setAddingFor(iso); };

  return (
    <div data-testid="transactions-calendar">
      <MonthGrid
        year={year}
        month={month}
        today={today}
        selected={selected}
        onDayClick={(iso) => onSelect(iso === selected ? null : iso)}
        onDayAdd={startAdding}
        cellClassName="min-h-[92px]"
        renderDay={(iso) => {
          const txs = byDay.get(iso);
          if (!txs) return null;
          const totals = data.days[iso];
          return (
            <>
              {txs.slice(0, SHOWN_PER_DAY).map((t) => (
                <div key={t.id} className="flex items-baseline gap-1 text-label leading-tight" title={`${t.desc || t.cat} · ${t.cat}`}>
                  <span className="min-w-0 flex-1 truncate text-ink-soft">{t.desc || t.cat}</span>
                  <span className={`num shrink-0 ${t.type === 'income' ? 'text-positive' : 'text-ink'}`}>
                    {t.type === 'income' ? `+${fmtMoney(t.amount, { round: true })}` : fmtMoney(t.amount, { round: true })}
                  </span>
                </div>
              ))}
              {txs.length > SHOWN_PER_DAY && (
                <div className="text-label text-ink-muted">+{txs.length - SHOWN_PER_DAY} more</div>
              )}
              {txs.length > 1 && totals && (
                <div className="num flex flex-wrap justify-end gap-x-1.5 whitespace-nowrap border-t border-line/70 pt-0.5 text-label font-medium">
                  {totals.income > 0 && <span className="text-positive">+{fmtMoney(totals.income, { round: true })}</span>}
                  {totals.expense > 0 && <span>−{fmtMoney(totals.expense, { round: true })}</span>}
                </div>
              )}
            </>
          );
        }}
      />

      {selected && dayTotals && (
        <div className="mt-4 overflow-hidden rounded-card border border-line" data-testid="calendar-day">
          <div className="flex items-center gap-3 px-4 pt-3">
            <h3 className="flex-1 text-card-title">{fmtDate(selected)}</h3>
            {!adding && (
              <button className="btn-secondary btn-sm" onClick={() => setAddingFor(selected)}>
                <Plus size={14} /> Add on this day
              </button>
            )}
            <button className="btn-ghost btn-sm" aria-label="Close day" onClick={() => onSelect(null)}><X size={14} /></button>
          </div>
          {adding && (
            <div className="mx-4 mt-3 rounded-lg bg-bg p-3" data-testid="calendar-add">
              <div className="mb-2 flex items-center">
                <h4 className="flex-1 text-xs font-semibold text-ink-soft">New transaction</h4>
                <button className="btn-ghost btn-sm" aria-label="Close new transaction" onClick={() => setAddingFor(null)}><X size={13} /></button>
              </div>
              <div className="max-w-md">
                <TransactionForm key={selected} year={year} initialDate={selected} idPrefix="day-tx" />
              </div>
            </div>
          )}
          {dayList.length > 0 ? (
            <TransactionTable
              year={year}
              grouped={false}
              selectable={false}
              footer={false}
              data={{
                transactions: [...dayList].reverse(),
                count: dayList.length,
                total_income: dayTotals.income,
                total_expense: dayTotals.expense,
                days: {},
              }}
            />
          ) : !adding && <p className="px-4 pb-4 pt-2 text-[13px] text-ink-soft">Nothing recorded on this day.</p>}
        </div>
      )}

      <div className="num mt-3 flex justify-end gap-5 text-[13px] text-ink-soft">
        <span>Cash in <strong className="font-semibold text-positive">{fmtMoney(data.total_income, { sign: true })}</strong></span>
        <span>Cash out <strong className="font-semibold text-ink">{fmtExpense(data.total_expense)}</strong></span>
      </div>
    </div>
  );
}
