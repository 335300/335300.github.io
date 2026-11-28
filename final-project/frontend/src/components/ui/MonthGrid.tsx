import { ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import type { ReactNode } from 'react';
import { MONTHS } from '../../lib/format';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const pad = (n: number) => String(n).padStart(2, '0');

/** "Month YYYY" with ‹ › buttons. Arrows are hidden when there is nowhere to go. */
export function MonthNav({ year, month, onPrev, onNext }: {
  year: number;
  month: number;
  onPrev?: () => void;
  onNext?: () => void;
}) {
  return (
    <div className="flex items-center gap-1">
      <button className="btn-icon h-7" aria-label="Previous month" onClick={onPrev} disabled={!onPrev}>
        <ChevronLeft size={16} aria-hidden />
      </button>
      <span className="num w-32 text-center text-body font-semibold" data-testid="calendar-month">{MONTHS[month]} {year}</span>
      <button className="btn-icon h-7" aria-label="Next month" onClick={onNext} disabled={!onNext}>
        <ChevronRight size={16} aria-hidden />
      </button>
    </div>
  );
}

/**
 * A Monday-first month calendar. It only lays out the days; what goes in a day
 * comes from `renderDay` (the figures in it come from the backend).
 */
export function MonthGrid({ year, month, today, renderDay, onDayClick, onDayAdd, selected, cellClassName = 'min-h-[88px]' }: {
  year: number;
  /** 0-11 */
  month: number;
  /** "YYYY-MM-DD" */
  today: string;
  renderDay: (iso: string) => ReactNode;
  onDayClick?: (iso: string) => void;
  /** Shows a small "+" on a day when the mouse is over it. */
  onDayAdd?: (iso: string) => void;
  selected?: string | null;
  cellClassName?: string;
}) {
  const first = new Date(year, month, 1);
  const lead = (first.getDay() + 6) % 7; // Monday = 0
  const days = new Date(year, month + 1, 0).getDate();
  const cells: (string | null)[] = [
    ...Array<null>(lead).fill(null),
    ...Array.from({ length: days }, (_, i) => `${year}-${pad(month + 1)}-${pad(i + 1)}`),
  ];
  while (cells.length % 7) cells.push(null);

  return (
    <div role="grid" aria-label={`${MONTHS[month]} ${year}`}>
      <div className="grid grid-cols-7 gap-px pb-1.5 text-center text-label text-ink-soft" role="row">
        {WEEKDAYS.map((d) => <div key={d} role="columnheader">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-card border border-line bg-line">
        {cells.map((iso, i) => {
          if (!iso) return <div key={`x${i}`} className={`bg-bg/60 ${cellClassName}`} aria-hidden />;
          const isToday = iso === today;
          const isSelected = iso === selected;
          const day = Number(iso.slice(8));
          const body = (
            <>
              <span className={`num inline-flex h-5 min-w-5 items-center justify-center self-start rounded-pill px-1 text-label ${
                isToday ? 'bg-primary font-semibold text-on-primary' : 'text-ink-soft'}`}>
                {day}
              </span>
              <div className="mt-0.5 w-full min-w-0 space-y-0.5">{renderDay(iso)}</div>
            </>
          );
          const cls = `relative flex min-w-0 flex-col justify-start overflow-hidden p-1 text-left ${cellClassName} ${
            isSelected ? 'bg-primary-tint ring-2 ring-inset ring-focus-ring' : 'bg-surface'}`;
          if (onDayClick) {
            const cell = (
              <button key={iso} type="button" role="gridcell" aria-selected={isSelected} aria-label={iso}
                data-day={iso} className={`${cls} w-full transition-colors duration-hover hover:bg-neutral-tint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus-ring`} onClick={() => onDayClick(iso)}>
                {body}
              </button>
            );
            if (!onDayAdd) return cell;
            return (
              <div key={iso} className="group relative flex">
                {cell}
                <button type="button" aria-label={`Add on ${iso}`} title="Add a transaction on this day"
                  className="absolute right-1 top-1 rounded-input p-0.5 text-ink-soft opacity-0 transition-opacity hover:bg-primary-tint hover:text-primary focus:opacity-100 group-hover:opacity-100"
                  onClick={() => onDayAdd(iso)}>
                  <Plus size={14} aria-hidden />
                </button>
              </div>
            );
          }
          return (
            <div key={iso} role="gridcell" data-day={iso} className={cls}>{body}</div>
          );
        })}
      </div>
    </div>
  );
}
