import type { CategoryKind } from '../../lib/types';

/**
 * The small coloured dot in front of a category name (as in Designs/).
 * One rule for the whole app, so a category has the same colour on every screen:
 * cash in → green, investments → violet, every other category → one of seven
 * chart colours picked from its name. Grey is left out: it means "no category".
 * Looks only — no money here.
 */

// Literal class names so Tailwind keeps them.
const DOTS = ['bg-chart-1', 'bg-chart-2', 'bg-chart-3', 'bg-chart-4', 'bg-chart-5', 'bg-chart-6', 'bg-chart-7'];

export function categoryDotClass(cat: string, kind?: CategoryKind, income = false): string {
  if (income) return 'bg-positive';
  if (kind === 'investment') return 'bg-invest';
  let h = 0;
  for (let i = 0; i < cat.length; i++) h = (h * 31 + cat.charCodeAt(i)) >>> 0;
  return DOTS[h % DOTS.length];
}

export function CategoryDot({ cat, kind, income = false, className = '' }: {
  cat: string;
  kind?: CategoryKind;
  /** A cash-in category (always green). */
  income?: boolean;
  className?: string;
}) {
  return (
    <span aria-hidden data-testid="category-dot"
      className={`inline-block h-2 w-2 shrink-0 rounded-full ${categoryDotClass(cat, kind, income)} ${className}`} />
  );
}
