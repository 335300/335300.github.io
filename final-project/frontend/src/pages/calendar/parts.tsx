import { CalendarDays, CalendarPlus, CalendarX, Check, X } from 'lucide-react';
import { useState } from 'react';
import { useAllowCalendar } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { MonthNav } from '../../components/ui/MonthGrid';
import { StatusText } from '../../components/ui/StatusBadge';
import { fmtDay, fmtMoney } from '../../lib/format';
import type { CalendarAccess, CalendarDay } from '../../lib/types';
import { EventChip, EventRow, LEGEND, MoneyChip, MoneyRow } from './look';

/* ---- Dates (calendar days, not money: plain date stepping is fine in the page) ---- */

const pad = (n: number) => String(n).padStart(2, '0');
export const isoOf = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const addDays = (iso: string, n: number) => {
  const [y, m, d] = iso.split('-').map(Number);
  return isoOf(new Date(y, m - 1, d + n));
};

const longFmt = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
/** "2026-11-21" → "Saturday, 21 November". */
export function fmtLongDay(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  const parts = longFmt.formatToParts(new Date(y, m - 1, d));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  return `${get('weekday')}, ${get('day')} ${get('month')}`;
}

export type Show = { events: boolean; money: boolean };

/** The month shown, the picked day and the filters. Opens on this month: the tab is about what comes next. */
export function useCalendarState(pickToday: boolean) {
  const today = isoOf(new Date());
  const [ym, setYm] = useState(() => ({ y: new Date().getFullYear(), m: new Date().getMonth() }));
  const [day, setDay] = useState<string | null>(pickToday ? today : null);
  const [show, setShow] = useState<Show>({ events: true, money: true });
  const move = (step: number) => {
    const n = ym.y * 12 + ym.m + step;
    setYm({ y: Math.floor(n / 12), m: n % 12 });
    setDay(null);
  };
  const goToday = () => {
    setYm({ y: new Date().getFullYear(), m: new Date().getMonth() });
    setDay(pickToday ? today : null);
  };
  const toggle = (key: keyof Show) => setShow((s) => ({ ...s, [key]: !s[key] }));
  const start = `${ym.y}-${pad(ym.m + 1)}-01`;
  const end = isoOf(new Date(ym.y, ym.m + 1, 0));
  const todayYm = { y: new Date().getFullYear(), m: new Date().getMonth() };
  // Which way the shown month lies from today: picks the sentence, nothing else.
  const when: 'past' | 'current' | 'future' =
    ym.y === todayYm.y && ym.m === todayYm.m ? 'current' : ym.y * 12 + ym.m < todayYm.y * 12 + todayYm.m ? 'past' : 'future';
  return { today, ym, day, setDay, show, toggle, move, goToday, start, end, when };
}

/** ‹ November 2026 › and Today. */
export function MonthControls({ year, month, onMove, onToday }: { year: number; month: number; onMove: (step: number) => void; onToday: () => void }) {
  return (
    <div className="flex shrink-0 items-center gap-2">
      <MonthNav year={year} month={month} onPrev={() => onMove(-1)} onNext={() => onMove(1)} />
      <button type="button" className="btn-ghost text-primary" onClick={onToday}>Today</button>
    </div>
  );
}

/* ---- Apple Calendar access (unchanged behaviour) ---- */

export function AccessBanner({ access, joint }: { access: CalendarAccess; joint: boolean }) {
  const allow = useAllowCalendar();
  if (access === 'not_asked') {
    return (
      <div className="flex items-center gap-3 rounded-card border border-primary/30 bg-primary-tint px-4 py-3 text-body" data-testid="calendar-access">
        <CalendarPlus size={18} className="shrink-0 text-primary" aria-hidden />
        <span className="flex-1">{joint ? 'See your Apple Calendar events next to our money dates.' : 'See your Apple Calendar events next to the money dates.'}</span>
        {allow.isPending
          ? <span className="text-label text-ink-soft">Waiting for your answer in the macOS window…</span>
          : <button className="btn-primary btn-sm" onClick={() => allow.mutate(undefined)}>Allow calendar access</button>}
        <ErrorNote error={allow.error} />
      </div>
    );
  }
  const off = access === 'denied' || access === 'restricted' || access === 'write_only';
  return (
    <div className="flex items-center gap-3 rounded-card border border-line bg-surface px-4 py-3 text-body" data-testid="calendar-access">
      <CalendarX size={18} className="shrink-0 text-ink-soft" aria-hidden />
      <span className="flex-1">
        {off
          ? 'Calendar access is off. To turn it on: System Settings → Privacy & Security → Calendars → Personal Centwise (Full Access).'
          : 'Apple Calendar cannot be read on this Mac. The money dates still show.'}
      </span>
    </div>
  );
}

/* ---- A day cell ---- */

export function DayCell({ day, show, max, tall = false }: { day?: CalendarDay; show: Show; max: number; tall?: boolean }) {
  if (!day) return null;
  const items = [
    ...(show.money ? day.money.map((m) => <MoneyChip key={m.key} m={m} tall={tall} />) : []),
    ...(show.events ? day.events.map((e) => <EventChip key={e.id} e={e} tall={tall} />) : []),
  ];
  return (
    <>
      {day.lecture && <span className="absolute inset-x-0 top-0 h-[3px] bg-info/45" title="Lecture period" aria-hidden />}
      {items.slice(0, max)}
      {items.length > max && <div className="px-1 text-label text-ink-muted">+{items.length - max} more</div>}
    </>
  );
}

/* ---- The day panel ---- */

export function DayPanel({ iso, day, show, today, onClose }: {
  iso: string;
  day?: CalendarDay;
  show: Show;
  today: string;
  onClose: () => void;
}) {
  const money = show.money ? day?.money ?? [] : [];
  const events = show.events ? day?.events ?? [] : [];
  const hidden = !money.length && !events.length && Boolean(day && (day.money.length || day.events.length));
  const sub = [iso === today ? 'Today' : iso > today ? 'Planned' : 'Past', day?.lecture ? 'Lecture period' : null].filter(Boolean).join(' · ');
  return (
    <section className="flex flex-col rounded-card border border-line bg-surface-raised shadow-card" data-testid="calendar-tab-day">
      <header className="flex items-start justify-between gap-2 px-4 pb-1 pt-4">
        <div className="flex min-w-0 flex-col gap-0.5">
          <h3 className="text-card-title">{fmtLongDay(iso)}</h3>
          <span className="text-label text-ink-soft">{sub}</span>
        </div>
        <button type="button" className="btn-icon" aria-label="Close day" onClick={onClose}><X size={15} aria-hidden /></button>
      </header>
      {!money.length && !events.length ? (
        <p className="px-4 pb-4 pt-3 text-[13px] text-ink-soft">{hidden ? 'Hidden by “Show in the calendar”.' : 'Nothing on this day.'}</p>
      ) : (
        <ul className="divide-y divide-line px-4 pb-2 pt-1">
          {money.map((m) => <MoneyRow key={m.key} m={m} />)}
          {events.map((e) => <EventRow key={e.id} e={e} />)}
        </ul>
      )}
      {/* "Balance after this day" waits for the backend to send it (not computed here). */}
    </section>
  );
}

/* ---- Show in the calendar: Money / Events, and the legend ---- */

export function ShowCard({ show, onToggle, joint }: { show: Show; onToggle: (key: keyof Show) => void; joint: boolean }) {
  return (
    <section className="flex flex-col gap-3 rounded-card border border-line bg-surface p-4 shadow-card">
      <h3 className="text-card-title">Show in the calendar</h3>
      <div className="flex flex-col gap-2.5" role="group" aria-label="Show in the calendar">
        <CheckToggle on={show.money} onClick={() => onToggle('money')} label="Money" note={joint ? 'bills, money in, goal dates' : 'bills, income, goal dates'} />
        <CheckToggle on={show.events} onClick={() => onToggle('events')} label="Events" note="from Apple Calendar" />
      </div>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-line pt-3" aria-label="Legend">
        {LEGEND.filter((l) => !joint || !l.personalOnly).map((l) => (
          <li key={l.word} className="flex items-center gap-1.5 text-label text-ink-soft"><span aria-hidden className="flex">{l.mark}</span>{l.word}</li>
        ))}
      </ul>
    </section>
  );
}

/** A switch that looks like a checkbox (a toggle button, so `aria-pressed` tells its state). */
function CheckToggle({ on, onClick, label, note }: { on: boolean; onClick: () => void; label: string; note: string }) {
  return (
    <button type="button" aria-pressed={on} onClick={onClick} className="flex items-center gap-2.5 text-left text-[13px] text-ink">
      <span aria-hidden className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border ${on ? 'border-primary bg-primary text-on-primary' : 'border-line-strong bg-surface'}`}>
        {on && <Check size={12} strokeWidth={3} />}
      </span>
      <span>{label} <span className="text-ink-soft">· {note}</span></span>
    </button>
  );
}

/* ---- Next 14 days ---- */

export function NextDays({ days, today, show, due, expected, error }: {
  days: CalendarDay[];
  today: string;
  show: Show;
  due?: number;
  expected?: number;
  error: unknown;
}) {
  const tomorrow = addDays(today, 1);
  const filled = days
    .map((d) => ({ ...d, money: show.money ? d.money : [], events: show.events ? d.events : [] }))
    .filter((d) => d.money.length || d.events.length);
  return (
    <section className="flex flex-col gap-2 rounded-card border border-line bg-surface p-4 shadow-card" data-testid="next-14-days">
      <h3 className="text-card-title">Next 14 days</h3>
      {error ? <ErrorNote error={error} /> : (
        <>
          {due !== undefined && expected !== undefined && (
            <div className="num flex flex-wrap gap-x-4 gap-y-1 text-label text-ink-soft">
              <span>Still to pay <strong className="font-semibold text-ink">{fmtMoney(due)}</strong></span>
              <span>Money expected <strong className="font-semibold text-ink">{fmtMoney(expected)}</strong></span>
            </div>
          )}
          {!filled.length ? (
            <p className="flex items-center gap-1.5 text-[13px] text-ink-soft"><CalendarDays size={14} aria-hidden /> Nothing in the next 14 days.</p>
          ) : (
            filled.map((d) => (
              <div key={d.date} className="pt-1">
                <h4 className="text-label text-ink-muted">{d.date === today ? 'Today' : d.date === tomorrow ? 'Tomorrow' : fmtDay(d.date)}</h4>
                <ul className="divide-y divide-line">
                  {d.money.map((m) => <MoneyRow key={m.key} m={m} compact />)}
                  {d.events.map((e) => <EventRow key={e.id} e={e} compact />)}
                </ul>
              </div>
            ))
          )}
        </>
      )}
    </section>
  );
}

/** "⚠ could not read the calendar" line, from the backend. */
export function EventsError({ text }: { text: string | null | undefined }) {
  return text ? <StatusText kind="warning">{text}</StatusText> : null;
}
