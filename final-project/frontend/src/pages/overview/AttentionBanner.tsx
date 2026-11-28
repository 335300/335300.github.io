import { useAttention, useAttentionMove } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { StatusBadge, type StatusKind } from '../../components/ui/StatusBadge';
import { showUndo } from '../../components/ui/UndoToast';
import { fmtMoney } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { Attention, Dashboard } from '../../lib/types';

const TINT: Record<StatusKind, string> = {
  positive: 'bg-positive-tint',
  warning: 'bg-warning-tint',
  negative: 'bg-negative-tint',
  info: 'bg-info-tint',
  neutral: 'bg-neutral-tint',
  reached: 'bg-surface',
};

const BADGE: Record<NonNullable<Attention['reason']>, { kind: StatusKind; word: string }> = {
  over: { kind: 'negative', word: 'Over budget' },
  pace: { kind: 'warning', word: 'On pace to go over' },
  close: { kind: 'warning', word: 'Close to limit' },
};

const CANNOT_MOVE: Record<NonNullable<Attention['cannot_move_reason']>, string | null> = {
  nothing_needed: null,
  no_room: 'No other variable budget has enough room this month.',
  fills_itself: 'One of these budgets follows a plan — change it in the budget plan.',
  linked: 'One of these budgets is linked to a % of income — change it in the budget plan.',
};

/** The headline sentence. Every amount comes from services/attention.py. */
function title(a: Attention): string {
  const cat = a.category ?? '';
  const budget = fmtMoney(a.budget ?? 0, { round: true });
  if (a.reason === 'over') return `${cat} is ${fmtMoney(a.over ?? 0, { round: true })} over its ${budget} budget.`;
  if (a.reason === 'pace') return `${cat} is heading over its ${budget} budget: about ${fmtMoney(a.pace ?? 0, { round: true })} by the end of the month.`;
  return `${cat} has ${fmtMoney(a.left ?? 0, { round: true })} of its ${budget} budget left for ${a.days_left} day${a.days_left === 1 ? '' : 's'}.`;
}

/**
 * "Worth a look" (Personal Overview): the one variable budget that needs a look
 * this month, with a one-click fix when the backend found a budget with room.
 * Only shown for the month that is running now (the API sends null otherwise).
 */
export function AttentionBanner({ year, month, rows }: {
  year: number;
  month: number;
  rows: Dashboard['budget_vs_real']['rows'];
}) {
  const { data } = useAttention(year, month);
  const move = useAttentionMove(year);
  const setTab = useUi((s) => s.setTab);
  if (!data || data.checked === 0) return null;

  if (data.status === 'all_clear') {
    return (
      <div className={`flex flex-wrap items-center gap-3 rounded-card px-4 py-3 ${TINT.positive}`} data-testid="attention-banner" role="status">
        <StatusBadge kind="positive">All on track</StatusBadge>
        <p className="text-body text-ink">
          <b className="font-semibold">Nothing needs your attention.</b>{' '}
          <span className="text-ink-soft">
            {data.checked === 1 ? 'Your variable budget is' : `All ${data.checked} variable budgets are`} within the limit this month.
          </span>
        </p>
      </div>
    );
  }

  const look = BADGE[data.reason ?? 'close'];
  // "Everything else is on track" only when no other budget row is flagged (a filter, no maths).
  const othersFine = !rows.some((r) => r.cat !== data.category && r.kind === 'variable' && (r.status === 'over' || r.status === 'warning'));
  const fix = data.can_move && data.source
    ? `Moving ${fmtMoney(data.needed, { round: true })} from ${data.source} covers it.`
    : data.cannot_move_reason ? CANNOT_MOVE[data.cannot_move_reason] : null;

  const apply = () => {
    if (!data.source || !data.category) return;
    const from = data.source;
    const to = data.category;
    const amount = data.needed;
    move.mutate({ month, from_cat: from, to_cat: to, amount }, {
      onSuccess: () => showUndo(`Moved ${fmtMoney(amount, { round: true })} of budget from ${from} to ${to}.`),
    });
  };

  return (
    <div className={`rounded-card px-4 py-3 ${TINT[look.kind]}`} data-testid="attention-banner" role="status">
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge kind={look.kind}>{look.word}</StatusBadge>
        <p className="num min-w-0 flex-1 text-body text-ink">
          <b className="font-semibold">{title(data)}</b>{' '}
          <span className="text-ink-soft">
            {fix}{fix && othersFine ? ' ' : ''}{othersFine ? 'Everything else is on track.' : ''}
          </span>
        </p>
        <div className="flex shrink-0 gap-2">
          <button type="button" className="btn-secondary btn-sm" onClick={() => setTab('forecast')}>Adjust budget</button>
          {data.can_move && data.source && (
            <button type="button" className="btn-secondary btn-sm" disabled={move.isPending} onClick={apply} data-testid="attention-move">
              Move {fmtMoney(data.needed, { round: true })} from {data.source}
            </button>
          )}
        </div>
      </div>
      <ErrorNote error={move.error} />
    </div>
  );
}
