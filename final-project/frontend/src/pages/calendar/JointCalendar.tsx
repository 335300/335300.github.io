import { useMemo } from 'react';
import { useBillsCalendar, useCalendarView, useMoneyDates } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { MonthGrid } from '../../components/ui/MonthGrid';
import { StatusIcon, StatusText } from '../../components/ui/StatusBadge';
import { Skeleton } from '../../components/ui/States';
import { fmtMoney, MONTHS } from '../../lib/format';
import type { BillsCalendar, MoneyDates } from '../../lib/types';
import { AccessBanner, addDays, DayCell, DayPanel, EventsError, fmtLongDay, MonthControls, NextDays, ShowCard, useCalendarState } from './parts';

/** Joint day cells hold two entries (each on two lines, 14px); the rest is "+N more". */
const CELL_ITEMS = 2;
/** How far ahead "Money expected" looks for the next monthly transfers. */
const EXPECTED_DAYS = 62;

/**
 * The Joint Calendar, in plain English for Isa: the bills of the month, whether
 * the money is there, and when the next monthly transfers come. Figures come from
 * the backend (recurring.month_calendar, money_dates, calendar_view); the page
 * only counts items to pick a sentence and formats.
 */
export function JointCalendar() {
  const s = useCalendarState(false);
  const month = useCalendarView(s.start, s.end);
  const next = useCalendarView(s.today, addDays(s.today, 13));
  const bills = useBillsCalendar(s.ym.y, s.ym.m);
  const ahead = useMoneyDates(s.today, addDays(s.today, EXPECTED_DAYS));
  const byDate = useMemo(() => new Map((month.data?.days ?? []).map((d) => [d.date, d])), [month.data]);
  const access = month.data?.access ?? next.data?.access;
  const monthName = MONTHS[s.ym.m];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-6">
        <Headline data={bills.data} error={bills.error} when={s.when} monthName={monthName} />
        <MonthControls year={s.ym.y} month={s.ym.m} onMove={s.move} onToday={s.goToday} />
      </div>

      {access && access !== 'full' && <AccessBanner access={access} joint />}

      <div className="grid grid-cols-[minmax(0,1fr)_300px] items-start gap-5">
        <div className="flex flex-col gap-4">
          <section className="rounded-card border border-line bg-surface p-3 shadow-card" data-testid="calendar-tab-month">
            {month.data?.events_error && <div className="mb-2"><EventsError text={month.data.events_error} /></div>}
            {month.error ? <ErrorNote error={month.error} /> : (
              <MonthGrid
                year={s.ym.y}
                month={s.ym.m}
                today={s.today}
                selected={s.day}
                onDayClick={s.setDay}
                cellClassName="min-h-[120px]"
                renderDay={(iso) => <DayCell day={byDate.get(iso)} show={s.show} max={CELL_ITEMS} tall />}
              />
            )}
          </section>
          {s.day && <DayPanel iso={s.day} day={byDate.get(s.day)} show={s.show} today={s.today} onClose={() => s.setDay(null)} />}
        </div>

        <div className="flex flex-col gap-5">
          <StillToPay data={bills.data} error={bills.error} when={s.when} monthName={monthName} />
          <MoneyExpected data={ahead.data} error={ahead.error} />
          <NextDays days={next.data?.days ?? []} today={s.today} show={s.show}
            due={next.data?.due_total} expected={next.data?.expected_total} error={next.error} />
          <ShowCard show={s.show} onToggle={s.toggle} joint />
        </div>
      </div>
    </div>
  );
}

type When = 'past' | 'current' | 'future';

/** "Our shared account · November" / "3 bills left this month — 310 € in total." / "✓ There is enough money…". */
function Headline({ data, error, when, monthName }: { data?: BillsCalendar; error: unknown; when: When; monthName: string }) {
  const open = (data?.bills ?? []).filter((b) => !b.paid);
  const n = open.length;
  const word = n === 1 ? 'bill' : 'bills';
  let sentence = '';
  if (data) {
    if (n === 0) {
      if (!data.bills.length) sentence = when === 'current' ? 'No bills this month.' : `No bills in ${monthName}.`;
      else sentence = when === 'current' ? 'All bills of this month are paid.' : when === 'past' ? `All bills of ${monthName} are paid.` : `No bills left to pay in ${monthName}.`;
    } else {
      const total = fmtMoney(data.total_due, { round: true });
      if (when === 'current') sentence = `${n} ${word} left this month — ${total} in total.`;
      else if (when === 'past') sentence = `${n} ${word} from ${monthName} not paid yet — ${total} in total.`;
      else sentence = `${n} ${word} to pay in ${monthName} — ${total} in total.`;
    }
  }
  // The backend judges each bill ("ready" = the free money covers it; null = too far ahead to say).
  const enough = n > 0 && open.every((b) => b.ready === true);
  const short = open.some((b) => b.ready === false);
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <span className="text-[15px] text-ink-soft">Our shared account · {monthName}</span>
      {error ? <ErrorNote error={error} /> : (
        <h1 className="text-[32px] font-semibold leading-10" data-testid="joint-calendar-headline">{sentence || '…'}</h1>
      )}
      {enough && (
        <span className="flex items-center gap-2 text-base text-ink-soft" data-testid="joint-calendar-enough">
          <StatusIcon kind="positive" size={18} className="text-positive" />There is enough money in the account for all of them.
        </span>
      )}
      {short && (
        <span className="flex items-center gap-2 text-base text-ink-soft" data-testid="joint-calendar-enough">
          <StatusIcon kind="warning" size={18} className="text-warning-ink" />There is not enough free money for all of them yet.
        </span>
      )}
    </div>
  );
}

/** The bills of the month not paid yet, in date order (the backend's list). */
function StillToPay({ data, error, when, monthName }: { data?: BillsCalendar; error: unknown; when: When; monthName: string }) {
  const open = (data?.bills ?? []).filter((b) => !b.paid);
  return (
    <section className="flex flex-col rounded-card border border-line bg-surface shadow-card" data-testid="joint-still-to-pay">
      <h3 className="px-5 pb-2 pt-5 text-lg font-semibold">Still to pay</h3>
      <div className="px-5 pb-5">
        {error ? <ErrorNote error={error} /> : !data ? <Skeleton lines={3} /> : !open.length ? (
          <p className="text-[15px] text-ink-soft">{when === 'current' ? 'Nothing left to pay this month.' : `Nothing left to pay in ${monthName}.`}</p>
        ) : (
          <ul className="divide-y divide-line">
            {open.map((b) => (
              <li key={`${b.bill_id}-${b.due}`} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5 py-2.5 text-[15px]">
                <span className="truncate font-medium">{b.name}</span>
                <span className="num text-right font-medium">{fmtMoney(b.amount)}</span>
                <span className="text-[14px] text-ink-soft">{fmtLongDay(b.due)}</span>
                <span className="text-right">
                  {b.overdue
                    ? <StatusText kind="negative">Late</StatusText>
                    : b.ready === false ? <StatusText kind="warning">Not enough yet</StatusText> : null}
                </span>
              </li>
            ))}
          </ul>
        )}
        {/* "Left after these" waits for the backend to send it (not computed here). */}
      </div>
    </section>
  );
}

/** The next monthly transfers into the shared account ("From Josu", "From Isa"), from the money dates. */
function MoneyExpected({ data, error }: { data?: MoneyDates; error: unknown }) {
  const coming = (data?.items ?? []).filter((m) => m.kind === 'contribution' && !m.done);
  const first = coming[0]?.date;
  const nextOnes = coming.filter((m) => m.date === first);
  return (
    <section className="flex flex-col gap-2 rounded-card border border-line bg-surface p-5 shadow-card" data-testid="joint-money-expected">
      <h3 className="text-lg font-semibold">Money expected</h3>
      {error ? <ErrorNote error={error} /> : !data ? <Skeleton lines={2} /> : !first ? (
        <p className="text-[15px] text-ink-soft">No monthly transfers planned in the next two months.</p>
      ) : (
        <>
          <p className="text-[15px] leading-[22px] text-ink-soft">Next monthly transfers, on <span className="font-semibold text-ink">{fmtLongDay(first)}</span>:</p>
          <ul className="flex flex-col gap-1">
            {nextOnes.map((m) => (
              <li key={m.key} className="flex items-baseline justify-between gap-3 text-[15px]">
                <span>{m.name}</span>
                <span className="num font-semibold">{fmtMoney(m.amount)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
