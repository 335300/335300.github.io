import { useMemo } from 'react';
import { useBills, useCalendarView } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { KpiTile } from '../../components/ui/KpiTile';
import { MonthGrid } from '../../components/ui/MonthGrid';
import { StatusText } from '../../components/ui/StatusBadge';
import { fmtDay, fmtMoney, MONTHS } from '../../lib/format';
import type { CalendarView, MoneyDateItem, Upcoming } from '../../lib/types';
import { JointCalendar } from './JointCalendar';
import { forMonth } from './look';
import { AccessBanner, addDays, DayCell, DayPanel, EventsError, MonthControls, NextDays, ShowCard, useCalendarState } from './parts';

/** At most this many entries in a day cell; the rest is "+N more". */
const CELL_ITEMS = 3;

/**
 * The Calendar tab: Apple Calendar events and the open profile's money dates
 * (salary, Transfer to Joint, money from each of us, bills, goal deadlines).
 * Every figure comes from the backend (services/money_dates.py, calendar_view.py,
 * recurring.py); the page only picks words and formats.
 */
export function CalendarPage({ joint }: { joint: boolean }) {
  return joint ? <JointCalendar /> : <PersonalCalendar />;
}

function PersonalCalendar() {
  const s = useCalendarState(true);
  const month = useCalendarView(s.start, s.end);
  const next = useCalendarView(s.today, addDays(s.today, 13));
  const bills = useBills();
  const byDate = useMemo(() => new Map((month.data?.days ?? []).map((d) => [d.date, d])), [month.data]);
  const access = month.data?.access ?? next.data?.access;

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-0.5">
          <h1 className="text-page-title">Calendar</h1>
          <span className="text-[13px] text-ink-soft">Bills, income and goal dates by day · your Apple Calendar next to it</span>
        </div>
        <MonthControls year={s.ym.y} month={s.ym.m} onMove={s.move} onToday={s.goToday} />
      </div>

      {access && access !== 'full' && <AccessBanner access={access} joint={false} />}

      <Summary view={month.data} upcoming={bills.data?.upcoming} monthName={MONTHS[s.ym.m]} today={s.today} />

      <div className="grid grid-cols-[minmax(0,1fr)_320px] items-start gap-4">
        <section className="rounded-card border border-line bg-surface p-3 shadow-card" data-testid="calendar-tab-month">
          {month.data?.events_error && <div className="mb-2"><EventsError text={month.data.events_error} /></div>}
          {month.error ? <ErrorNote error={month.error} /> : (
            <MonthGrid
              year={s.ym.y}
              month={s.ym.m}
              today={s.today}
              selected={s.day}
              onDayClick={s.setDay}
              cellClassName="min-h-[124px]"
              renderDay={(iso) => <DayCell day={byDate.get(iso)} show={s.show} max={CELL_ITEMS} />}
            />
          )}
        </section>

        <div className="flex flex-col gap-4">
          {s.day
            ? <DayPanel iso={s.day} day={byDate.get(s.day)} show={s.show} today={s.today} onClose={() => s.setDay(null)} />
            : <p className="rounded-card border border-line bg-surface-raised px-4 py-4 text-[13px] text-ink-soft shadow-card">Pick a day to see what is on it.</p>}
          <ShowCard show={s.show} onToggle={s.toggle} joint={false} />
          <NextDays days={next.data?.days ?? []} today={s.today} show={s.show}
            due={next.data?.due_total} expected={next.data?.expected_total} error={next.error} />
        </div>
      </div>
    </div>
  );
}

/**
 * The three numbers on top. Values are the backend's (due_total, expected_total,
 * upcoming.liquidity); the lines under them only count and pick items to name.
 */
function Summary({ view, upcoming, monthName, today }: { view?: CalendarView; upcoming?: Upcoming; monthName: string; today: string }) {
  const items = (view?.days ?? []).flatMap((d) => d.money);
  const toPay = items.filter((m) => m.direction === 'out' && !m.done);
  const overdue = toPay.filter((m) => m.status === 'overdue').length;
  const nextPay = toPay.find((m) => m.status !== 'overdue' && m.date >= today);
  const salary = items.filter((m) => m.kind === 'salary');
  const salaryDue = salary.find((m) => !m.done);
  const salaryDone = salary.find((m) => m.done);

  const payMeta = !view ? null : !toPay.length
    ? <StatusText kind="positive">Nothing left to pay</StatusText>
    : (
      <span className="flex flex-wrap items-center gap-x-2">
        <span>{toPay.length} {toPay.length === 1 ? 'payment' : 'payments'}{nextPay ? ` · next on ${fmtDay(nextPay.date)}` : ''}</span>
        {overdue > 0 && <StatusText kind="negative">{overdue} overdue</StatusText>}
      </span>
    );

  const salaryWord = (m: MoneyDateItem) => ['Salary', forMonth(m)].filter(Boolean).join(' ');
  const inMeta = !view ? null
    : salaryDue ? `${salaryWord(salaryDue)} expected on ${fmtDay(salaryDue.date)}`
    : salaryDone ? <StatusText kind="positive">{`${salaryWord(salaryDone)} arrived`}</StatusText>
    : null;

  const freeMeta = !upcoming ? null : !upcoming.items.length
    ? `No bills in the next ${upcoming.days} days`
    : upcoming.all_ready
      ? <StatusText kind="positive">Bills of the next {upcoming.days} days are covered</StatusText>
      : <StatusText kind="warning">Not enough for every bill in the next {upcoming.days} days</StatusText>;

  return (
    <div className="grid grid-cols-3 gap-4" data-testid="calendar-summary">
      <KpiTile variant="compact" label={`Still to pay in ${monthName}`} value={view ? fmtMoney(view.due_total) : '…'} meta={payMeta} testId="calendar-kpi-due" />
      <KpiTile variant="compact" label="Money expected" value={view ? fmtMoney(view.expected_total) : '…'} meta={inMeta} testId="calendar-kpi-expected" />
      <KpiTile variant="compact" label="Free to use" value={upcoming ? fmtMoney(upcoming.liquidity) : '…'}
        tone={upcoming && upcoming.liquidity < 0 ? 'negative' : 'neutral'}
        meta={freeMeta} testId="calendar-kpi-free" />
    </div>
  );
}
