import { useCategories } from '../../api/queries';
import { categoryDotClass } from '../../components/ui/CategoryDot';
import { MONTHS } from '../../lib/format';
import type { CategoryKind } from '../../lib/types';

/**
 * Display helpers for the Transactions screen: which dot colour a category
 * gets and how a day heading reads. No money here — only looks and words.
 */

/** The category's dot colour — the one shared rule in components/ui/CategoryDot. */
export function dotClass(cat: string, kind?: CategoryKind, income = false): string {
  return categoryDotClass(cat, kind, income);
}

/** Category name → kind (fixed / variable / investment), for chips and dots. */
export function useCategoryKinds(year: number): Map<string, CategoryKind> {
  const { data } = useCategories(year);
  const map = new Map<string, CategoryKind>();
  for (const c of [...(data?.income ?? []), ...(data?.expense ?? [])]) map.set(c.name, c.kind);
  return map;
}

/** A category as a small pill with its dot; investments in violet. */
export function chipClass(kind?: CategoryKind): string {
  return kind === 'investment' ? 'chip bg-invest-tint text-invest' : 'chip';
}

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function parts(iso: string) {
  const [y, m, d] = iso.split('-').map(Number);
  return { y, m, d, wd: new Date(y, m - 1, d).getDay() };
}

/** "Thu 19.11." — Personal day headings. */
export function shortDay(iso: string): string {
  const { m, d, wd } = parts(iso);
  return `${WEEKDAYS[wd].slice(0, 3)} ${String(d).padStart(2, '0')}.${String(m).padStart(2, '0')}.`;
}

/** "Thursday, 19 November" — Joint day headings (plain words for Isa). */
export function longDay(iso: string): string {
  const { m, d, wd } = parts(iso);
  return `${WEEKDAYS[wd]}, ${d} ${MONTHS[m - 1]}`;
}

/** Last calendar day of a month (month 0–11). */
export function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

/** Rows grouped by date, keeping the order the backend sent (newest first). */
export function groupByDay<T extends { date: string }>(rows: T[]): [string, T[]][] {
  const groups: [string, T[]][] = [];
  for (const r of rows) {
    const last = groups[groups.length - 1];
    if (last && last[0] === r.date) last[1].push(r);
    else groups.push([r.date, [r]]);
  }
  return groups;
}
