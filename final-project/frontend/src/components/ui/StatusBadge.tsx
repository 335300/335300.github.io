import { CircleAlert, CircleCheck, CircleMinus, CircleX, Info, Star } from 'lucide-react';
import type { ReactNode } from 'react';
import type { BudgetStatus, GoalState } from '../../lib/types';

/**
 * The five status looks of the style guide, plus "reached" for celebrations.
 * Every status has an icon AND a word — never colour alone (WCAG 1.4.1).
 *   positive ✓ on track · warning ! close to limit · negative × over
 *   info i · neutral – · reached ★ (gold, only for a reached goal)
 */
export type StatusKind = 'positive' | 'warning' | 'negative' | 'info' | 'neutral' | 'reached';

const ICON: Record<StatusKind, typeof CircleCheck> = {
  positive: CircleCheck,
  warning: CircleAlert,
  negative: CircleX,
  info: Info,
  neutral: CircleMinus,
  reached: Star,
};

/** Text colour of each look (used on its own, or on the tint below). */
export const STATUS_TEXT: Record<StatusKind, string> = {
  positive: 'text-positive',
  warning: 'text-warning-ink',
  negative: 'text-negative',
  info: 'text-info',
  neutral: 'text-ink-soft',
  reached: 'text-gold-ink',
};

const BADGE_BG: Record<StatusKind, string> = {
  positive: 'bg-positive-tint',
  warning: 'bg-warning-tint',
  negative: 'bg-negative-tint',
  info: 'bg-info-tint',
  neutral: 'bg-neutral-tint',
  reached: 'bg-surface border border-gold',
};

/** The 14–16px status glyph. Decorative: the word next to it carries the meaning. */
export function StatusIcon({ kind, size = 14, className = '' }: { kind: StatusKind; size?: number; className?: string }) {
  const Icon = ICON[kind];
  return <Icon size={size} strokeWidth={2} aria-hidden className={`shrink-0 ${className}`} fill={kind === 'reached' ? 'currentColor' : 'none'} />;
}

/** A status chip: 24px tall, radius 6, tint background, icon + word. */
export function StatusBadge({ kind, children, detail, testId }: {
  kind: StatusKind;
  /** The word(s): "On track", "Close to limit", "Over budget"… */
  children: ReactNode;
  /** Optional extra after a dot, e.g. "€138 left". */
  detail?: ReactNode;
  testId?: string;
}) {
  return (
    <span
      data-testid={testId}
      className={`inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-input pl-[5px] pr-2 text-label ${BADGE_BG[kind]} ${STATUS_TEXT[kind]}`}
    >
      <StatusIcon kind={kind} />
      {children}
      {detail && <span className="num">· {detail}</span>}
    </span>
  );
}

/** Icon + word without a background, for lines under bars ("On track · €138 left"). */
export function StatusText({ kind, children, className = '' }: { kind: StatusKind; children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-label ${STATUS_TEXT[kind]} ${className}`}>
      <StatusIcon kind={kind} size={13} />
      <span className="num">{children}</span>
    </span>
  );
}

/* ---- Budget and goal statuses from the backend ---- */

/** Which look a backend budget status gets. */
export const budgetKind = (s: BudgetStatus): StatusKind =>
  s === 'over' ? 'negative' : s === 'warning' ? 'warning' : s === 'unbudgeted' ? 'neutral' : 'positive';

const BUDGET_WORD: Record<BudgetStatus, string> = {
  under: 'Within budget',
  on_budget: 'On budget',
  warning: 'Close to limit',
  over: 'Over budget',
  unbudgeted: 'No budget',
};

export function BudgetBadge({ status, detail, word }: {
  status: BudgetStatus;
  detail?: string;
  /** Replace the default word (e.g. "Heads-up" or "Over by 12 €"). */
  word?: string;
}) {
  return <StatusBadge kind={budgetKind(status)} detail={detail}>{word ?? BUDGET_WORD[status]}</StatusBadge>;
}

const GOAL: Record<GoalState, { kind: StatusKind; word: string }> = {
  on_track: { kind: 'positive', word: 'On track' },
  behind: { kind: 'warning', word: 'Behind' },
  met: { kind: 'reached', word: 'Goal reached' },
  overdue: { kind: 'negative', word: 'Overdue' },
  completed: { kind: 'neutral', word: 'Completed' },
  abandoned: { kind: 'neutral', word: 'Stopped' },
};

export function GoalBadge({ status, word }: { status: GoalState; word?: string }) {
  const look = GOAL[status];
  return <StatusBadge kind={look.kind}>{word ?? look.word}</StatusBadge>;
}

/** Bar colour for a budget status (ProgressBar tone). */
export const budgetBarTone = (s: BudgetStatus) =>
  s === 'over' ? 'negative' : s === 'warning' ? 'warning' : s === 'unbudgeted' ? 'neutral' : 'secondary';
