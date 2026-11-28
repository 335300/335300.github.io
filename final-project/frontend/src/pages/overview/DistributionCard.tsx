import { AlertTriangle, ArrowDown, ArrowUp, Check, Split } from 'lucide-react';
import { useState } from 'react';
import { Card, EmptyState } from '../../components/ui/Card';
import { fmtMoney, fmtPct } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { Distribution, JobBlock, SegmentKey } from '../../lib/types';
import { DistributeModal } from './DistributeModal';

const SEGMENT: Record<SegmentKey, string> = {
  fixed: 'bg-primary',
  variable: 'bg-secondary',
  investment: 'bg-invest',
  goals: 'bg-positive',
  unassigned: 'bg-ink-muted/30',
};

type Block = JobBlock;

/** "50–60%", "10% or more", "up to 35%". */
export function guideText(b: Block): string {
  if (b.guide_min !== null && b.guide_max !== null) return `${b.guide_min}–${b.guide_max}%`;
  if (b.guide_min !== null) return `${b.guide_min}% or more`;
  return `up to ${b.guide_max}%`;
}

/**
 * Where the month's income went: every euro by the job it got, against a
 * common planning guide, plus what is still waiting for a job.
 */
export function DistributionCard({ data, year, className }: { data: Distribution; year: number; className?: string }) {
  const [open, setOpen] = useState(false);
  const setTab = useUi((s) => s.setTab);
  const empty = data.income === 0 && data.cash_out === 0;
  const savings = data.blocks.find((b) => b.key === 'savings');

  return (
    <Card
      className={className}
      title="Where your income went"
      collapseKey="overview-distribution"
      collapseLabel="Where your income went"
    >
      {empty ? (
        <EmptyState title="Nothing recorded this month yet" />
      ) : (
        <>
          <div className="flex h-5 w-full overflow-hidden rounded-md bg-bg" role="img" data-testid="distribution-bar"
            aria-label={data.segments.map((s) => `${s.label} ${fmtMoney(s.amount)}`).join(', ')}>
            {data.segments.filter((s) => s.width > 0).map((s) => (
              <div key={s.key} className={`${SEGMENT[s.key]} h-full border-r border-surface last:border-0`} style={{ width: `${s.width}%` }}
                title={`${s.label}: ${fmtMoney(s.amount)} · ${fmtPct(s.share)} of income`} />
            ))}
          </div>
          <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-soft">
            {data.segments.map((s) => (
              <li key={s.key} className="flex items-center gap-1.5">
                <span className={`h-2.5 w-2.5 rounded-sm ${SEGMENT[s.key]}`} aria-hidden />
                {s.label} <span className="num font-medium text-ink">{fmtMoney(s.amount)}</span>
              </li>
            ))}
          </ul>

          <div className="mt-4 grid grid-cols-2 gap-4 border-t border-line pt-4">
            {data.blocks.map((b) => (
              <div key={b.key}>
                <div className="text-xs font-medium text-ink-soft">{b.label}</div>
                <div className={`num mt-0.5 text-lg font-semibold ${b.amount < 0 ? 'text-negative' : ''}`}>{fmtMoney(b.amount)}</div>
                <div className="num text-xs text-ink-muted">{data.income ? `${fmtPct(b.share)} of income` : 'No income recorded'}</div>
                {b.status && <GuideChip block={b} />}
                {b.key === 'savings' && data.saved > 0 && (
                  <div className="num mt-1.5 text-xs text-ink-muted">
                    {fmtMoney(data.to_goals)} to goals · {fmtMoney(data.left_to_assign)} not assigned
                  </div>
                )}
              </div>
            ))}
          </div>

          {data.shortfall > 0 && (
            <Note tone="warning">
              <strong className="num">{fmtMoney(data.shortfall)}</strong> more went out than came in this month — it came from the
              balance you already had.
            </Note>
          )}
          {data.shortfall === 0 && data.over_assigned && (
            <Note tone="warning">
              More is put toward goals than this month kept ({fmtMoney(data.to_goals)} of {fmtMoney(data.saved)}) — the rest
              comes from the balance you already had.
            </Note>
          )}
          {data.left_to_assign > 0 && (
            <div className="mt-4 flex items-center gap-3 rounded-lg border border-secondary/30 bg-secondary-tint px-4 py-3">
              <Split size={16} className="shrink-0 text-secondary" />
              <p className="flex-1 text-sm text-ink">
                <strong className="num">{fmtMoney(data.left_to_assign)}</strong> of {data.month_name}’s savings has no job yet.
                {savings && savings.amount > 0 && ' Give it one, or leave it as a buffer.'}
              </p>
              {data.suggested.length ? (
                <button className="btn-primary btn-sm" onClick={() => setOpen(true)}>Distribute to goals</button>
              ) : (
                <button className="btn-secondary btn-sm" onClick={() => setTab('forecast')}>Add a goal</button>
              )}
            </div>
          )}
        </>
      )}
      {open && <DistributeModal year={year} data={data} onClose={() => setOpen(false)} />}
    </Card>
  );
}

/** The planning range and where this month sits — an icon and a word, never colour alone. */
export function GuideChip({ block }: { block: Block }) {
  const look = block.attention
    ? 'bg-warning-tint text-warning'
    : block.status === 'within'
      ? 'bg-secondary-tint text-secondary'
      : 'bg-neutral-tint text-ink-soft';
  const icon = block.status === 'within' ? <Check size={12} /> : block.status === 'above' ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
  const word = block.status === 'within' ? 'In range' : block.status === 'above' ? 'Above' : 'Below';
  return (
    <span className={`mt-1.5 inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${look}`}>
      {icon}
      {word}
      <span className="num font-normal">· guide {guideText(block)}</span>
    </span>
  );
}

function Note({ tone, children }: { tone: 'warning'; children: React.ReactNode }) {
  return (
    <div className={`mt-4 flex items-start gap-2 rounded-lg px-3 py-2.5 text-sm ${tone === 'warning' ? 'bg-warning-tint text-warning' : ''}`}>
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <p>{children}</p>
    </div>
  );
}
