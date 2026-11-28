import { Circle, CircleAlert, CircleCheck, Flag, Plus } from 'lucide-react';
import type { ReactNode } from 'react';
import { StatusBadge, StatusText, type StatusKind } from '../../components/ui/StatusBadge';
import { fmtDate, fmtMoney, MONTHS } from '../../lib/format';
import type { CalendarEvent, MoneyDateItem } from '../../lib/types';

/*
 * How the Calendar tab's items look. Every figure comes from the backend
 * (services/money_dates.py, calendar_view.py); this file only picks a tone, an
 * icon and a word from the status the backend sent, and formats the amount.
 */

const MINUS = '−';

/** The amount with its direction: "+3.420 €" in, "−1.150 €" out, "500 €" for a goal (formatting only). */
export function moneyAmount(m: MoneyDateItem, round = false): string {
  if (m.direction === 'in') return fmtMoney(m.amount, { round, sign: true });
  if (m.direction === 'out') return `${MINUS}${fmtMoney(m.amount, { round })}`;
  return fmtMoney(m.amount, { round });
}

/** Chip tone and icon in a day cell. Colour never alone: the icon and the day panel's word carry it too. */
export function chipLook(m: MoneyDateItem, size = 12): { cls: string; icon: ReactNode } {
  if (m.status === 'overdue') return { cls: 'bg-negative-tint text-negative', icon: <CircleAlert size={size} aria-hidden /> };
  if (m.direction === 'goal') {
    return m.done
      ? { cls: 'bg-secondary-tint text-ink-soft', icon: <CircleCheck size={size} aria-hidden /> }
      : { cls: 'bg-secondary-tint text-secondary', icon: <Flag size={size} aria-hidden /> };
  }
  if (m.direction === 'in') {
    return { cls: 'bg-positive-tint text-positive', icon: m.done ? <CircleCheck size={size} aria-hidden /> : <Plus size={size} aria-hidden /> };
  }
  return m.done
    ? { cls: 'bg-neutral-tint text-ink-soft', icon: <CircleCheck size={size} aria-hidden /> }
    : { cls: 'bg-neutral-tint text-ink', icon: <Circle size={size} aria-hidden /> };
}

/** The status word (and badge look) of a money date, from the status the backend sent. */
export function moneyStatus(m: MoneyDateItem): { kind: StatusKind; word: string } {
  switch (m.kind) {
    case 'bill':
      if (m.done) return { kind: 'neutral', word: 'Paid' };
      return m.status === 'overdue' ? { kind: 'negative', word: 'Overdue' } : { kind: 'info', word: 'Still to pay' };
    case 'transfer':
      if (m.done) return { kind: 'neutral', word: 'Sent' };
      return m.status === 'overdue' ? { kind: 'negative', word: 'Not sent yet' } : { kind: 'info', word: 'To send' };
    case 'salary':
    case 'contribution':
      return m.done ? { kind: 'positive', word: 'Arrived' } : { kind: 'info', word: 'Money expected' };
    default:
      if (m.done) return { kind: 'reached', word: 'Goal reached' };
      return m.status === 'overdue' ? { kind: 'negative', word: 'Goal date passed' } : { kind: 'neutral', word: 'Goal deadline' };
  }
}

/** "for December" when the money is for a month (salary, transfer, money from each of us). */
export function forMonth(m: MoneyDateItem): string | null {
  return m.for_month ? `for ${MONTHS[Number(m.for_month.slice(5, 7)) - 1]}` : null;
}

/** The quiet line under an item: what it is, which month it is for, when it was paid. */
export function moneyMeta(m: MoneyDateItem): string {
  const parts: string[] = [];
  if (m.kind === 'bill') parts.push(m.paid_on ? `Paid on ${fmtDate(m.paid_on, { short: true })}` : 'Bill');
  if (m.kind === 'goal') parts.push('Savings goal');
  if (m.kind === 'sinking') parts.push('Sinking fund');
  const month = forMonth(m);
  if (month) parts.push(month);
  return parts.join(' · ');
}

/** "10:00" from "2026-11-18T10:00". */
export const timeOf = (when: string) => when.slice(11, 16);

/** "10:00–11:30", "All day", or "All day, until 21.11.". */
export function eventWhen(e: CalendarEvent): string {
  if (e.all_day) return e.end > e.start ? `All day, until ${fmtDate(e.end, { short: true })}` : 'All day';
  return `${timeOf(e.start)}–${timeOf(e.end)}`;
}

/* ---- Day cells ---- */

/** A money date inside a day cell: icon, name, amount. `tall` = Joint (two lines, 14px). */
export function MoneyChip({ m, tall = false }: { m: MoneyDateItem; tall?: boolean }) {
  const look = chipLook(m);
  const status = moneyStatus(m);
  // In a narrow cell "From Isa" would be cut to "From I…": the + already says money in.
  const name = m.kind === 'contribution' && !tall ? m.name.replace(/^From /, '') : m.name;
  const title = [m.name, moneyAmount(m), forMonth(m), status.word].filter(Boolean).join(' · ');
  if (tall) {
    return (
      <div className={`flex flex-col rounded-input px-1.5 py-0.5 text-[14px] font-medium leading-[18px] ${look.cls}`} title={title}>
        <span className="flex min-w-0 items-center gap-1"><span className="shrink-0">{look.icon}</span><span className="truncate">{name}</span></span>
        <span className="num">{moneyAmount(m, true)}</span>
      </div>
    );
  }
  return (
    <div className={`flex h-5 items-center gap-1 rounded-[4px] px-1 text-label ${look.cls}`} title={title}>
      <span className="flex w-3 shrink-0 justify-center">{look.icon}</span>
      <span className="min-w-0 flex-1 truncate">{name}</span>
      <span className="num shrink-0">{moneyAmount(m, true)}</span>
    </div>
  );
}

/**
 * An Apple Calendar event inside a day cell: a line in its calendar's own colour, the title, the time.
 * The colour is the calendar's (data from Apple Calendar), not a status.
 */
export function EventChip({ e, tall = false }: { e: CalendarEvent; tall?: boolean }) {
  return (
    <div className={`flex items-center gap-1 rounded-[4px] border-l-2 pl-1 pr-0.5 text-ink-soft ${tall ? 'min-h-5 text-[14px] leading-[18px]' : 'h-5 text-label'}`}
      style={{ borderLeftColor: e.color }}
      title={`${e.title} · ${eventWhen(e)} · ${e.calendar}${e.location ? ` · ${e.location}` : ''}`}>
      <span className="min-w-0 flex-1 truncate">{e.title}</span>
      {!e.all_day && <span className="num shrink-0 text-ink-muted">{timeOf(e.start)}</span>}
    </div>
  );
}

/* ---- Rows (day panel, next 14 days) ---- */

/** One money date as a row: name and amount, then a status badge and the quiet line. */
export function MoneyRow({ m, compact = false }: { m: MoneyDateItem; compact?: boolean }) {
  const status = moneyStatus(m);
  const meta = moneyMeta(m);
  return (
    <li className={`flex flex-col gap-1 ${compact ? 'py-2' : 'py-2.5'}`}>
      <div className="flex items-baseline justify-between gap-2 text-[13px]">
        <span className="min-w-0 truncate font-medium">{m.name}</span>
        <span className={`num shrink-0 font-semibold ${m.direction === 'in' ? 'text-positive' : 'text-ink'}`}>{moneyAmount(m)}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        {compact ? <StatusText kind={status.kind}>{status.word}</StatusText> : <StatusBadge kind={status.kind}>{status.word}</StatusBadge>}
        {meta && <span className="min-w-0 truncate text-label text-ink-soft">{meta}</span>}
      </div>
    </li>
  );
}

/** One Apple Calendar event as a row: title and time, then "Event" and its calendar. */
export function EventRow({ e, compact = false }: { e: CalendarEvent; compact?: boolean }) {
  return (
    <li className={`flex flex-col gap-1 ${compact ? 'py-2' : 'py-2.5'}`}>
      <div className="flex items-baseline justify-between gap-2 text-[13px]">
        <span className="min-w-0 truncate font-medium">{e.title}</span>
        <span className="num shrink-0 text-ink-soft">{eventWhen(e)}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        {compact
          ? <span className="inline-flex items-center gap-1.5 text-label text-ink-soft"><span className="h-3 w-0.5 rounded-pill" style={{ backgroundColor: e.color }} aria-hidden />Event</span>
          : <StatusBadge kind="neutral">Event</StatusBadge>}
        <span className="flex min-w-0 items-center gap-1.5 truncate text-label text-ink-soft">
          {!compact && <span className="h-2 w-2 shrink-0 rounded-pill" style={{ backgroundColor: e.color }} aria-hidden />}
          <span className="truncate">{e.calendar}{e.location ? ` · ${e.location}` : ''}</span>
        </span>
      </div>
    </li>
  );
}

/* ---- Legend ---- */

export type LegendItem = { word: string; mark: ReactNode; personalOnly?: boolean };

const swatch = 'inline-flex h-4 w-5 items-center justify-center rounded-[4px]';

export const LEGEND: LegendItem[] = [
  { word: 'Still to pay', mark: <span className={`${swatch} bg-neutral-tint text-ink`}><Circle size={11} /></span> },
  { word: 'Paid or arrived', mark: <span className={`${swatch} bg-neutral-tint text-ink-soft`}><CircleCheck size={11} /></span> },
  { word: 'Money expected', mark: <span className={`${swatch} bg-positive-tint text-positive`}><Plus size={11} /></span> },
  { word: 'Overdue', mark: <span className={`${swatch} bg-negative-tint text-negative`}><CircleAlert size={11} /></span> },
  { word: 'Goal deadline', mark: <span className={`${swatch} bg-secondary-tint text-secondary`}><Flag size={11} /></span> },
  { word: 'Calendar event (its colour)', mark: <span className={`${swatch} border-l-2 border-ink-muted`} /> },
  // The same light line that sits on top of a lecture day.
  { word: 'Lecture period (top line)', mark: <span className={`${swatch} relative overflow-hidden bg-neutral-tint`}><span className="absolute inset-x-0 top-0 h-[3px] bg-info/45" /></span>, personalOnly: true },
];
