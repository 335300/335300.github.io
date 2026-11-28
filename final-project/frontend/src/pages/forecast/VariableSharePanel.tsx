import { SlidersHorizontal, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useSetRowShare } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { fmtMoney, fmtPct, MONTHS_SHORT } from '../../lib/format';
import type { Range, SharePanel } from '../../lib/types';

const MAX_PCT = 40;

/** "€146 – €285", or one amount when both ends match. */
function money(r: Range | null): string {
  if (!r) return '—';
  const a = fmtMoney(r.min, { round: true });
  const b = fmtMoney(r.max, { round: true });
  return a === b ? a : `${a} – ${b}`;
}

/** "12–25%", from backend shares. */
function pct(r: Range | null): string {
  if (!r) return '—';
  const f = (v: number) => fmtPct(v, Number.isInteger(v) ? 0 : 1).replace('%', '');
  return r.min === r.max ? `${f(r.min)}%` : `${f(r.min)}–${f(r.max)}%`;
}

/**
 * One slider per variable cost: the % of each month's planned income it gets in
 * every month not recorded yet. The euros follow the income automatically (the
 * backend keeps them linked). Fixed costs and investment stay fixed amounts and
 * are shown for reference. Every figure comes from the backend; while a slider
 * is dragged only the % moves, the euros refresh once it is let go.
 */
export function VariableSharePanel({ year, panel }: { year: number; panel: SharePanel }) {
  const save = useSetRowShare(year);
  const months = panel.months;

  return (
    <section className="rounded-card border border-line p-4" aria-label="Variable costs by % of income" data-testid="share-panel">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-card-title"><SlidersHorizontal size={14} /> Variable costs by % of income</h3>
        {months.length > 0 && (
          <p className="num text-xs text-ink-muted">
            Coming months: {MONTHS_SHORT[months[0]]}{months.length > 1 ? ` – ${MONTHS_SHORT[months[months.length - 1]]}` : ''} {year}
            {' · '}income {money(panel.income)}
          </p>
        )}
      </div>

      {months.length === 0 ? (
        <p className="mt-3 text-sm text-ink-muted">Every month of {year} is already recorded. Pick next year to plan ahead.</p>
      ) : (
        <>
          <dl className="mt-3 grid grid-cols-[1fr_auto_auto] gap-x-6 gap-y-1 border-b border-line pb-3 text-sm">
            <Reference label="Fixed costs (fixed amounts)" amount={panel.fixed.amount} share={panel.fixed.share} />
            <Reference label="Investment (fixed amount)" amount={panel.investment.amount} share={panel.investment.share} />
          </dl>

          {panel.rows.length === 0 ? (
            <p className="mt-3 text-sm text-ink-muted">No variable categories yet. Add some in the Transactions tab.</p>
          ) : (
            <ul className="mt-3 space-y-1.5">
              {panel.rows.map((r) => (
                <SliderRow key={r.cat} row={r} onSave={(p) => save.mutate({ cat: r.cat, percent: p })} />
              ))}
            </ul>
          )}

          <div className="num mt-3 flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-line pt-3 text-sm" data-testid="share-panel-totals">
            <span>Variable costs <strong>{pct(panel.variable.share)}</strong> of income <span className="text-ink-muted">({money(panel.variable.amount)} a month)</span></span>
            <span>
              Left for savings <strong className={panel.savings.share && panel.savings.share.min < 0 ? 'text-negative' : 'text-positive'}>{pct(panel.savings.share)}</strong>
              {panel.savings.guide_min !== null && <span className="text-ink-muted"> · guide {panel.savings.guide_min}% or more</span>}
            </span>
          </div>
          {panel.savings.share && panel.savings.share.min < 0 && (
            <p className="mt-2 rounded-md bg-warning-tint px-3 py-1.5 text-label text-warning-ink">
              ⚠ In at least one coming month the plan spends more than that month’s income. Lower a slider or check the fixed amounts.
            </p>
          )}
        </>
      )}
      <ErrorNote error={save.error} />
    </section>
  );
}

function Reference({ label, amount, share }: { label: string; amount: Range | null; share: Range | null }) {
  return (
    <>
      <dt className="text-ink-soft">{label}</dt>
      <dd className="num text-right">{money(amount)} <span className="text-xs text-ink-muted">a month</span></dd>
      <dd className="num text-right text-xs text-ink-muted">≈ {pct(share)} of income</dd>
    </>
  );
}

function SliderRow({ row, onSave }: { row: SharePanel['rows'][number]; onSave: (percent: number | null) => void }) {
  const saved = row.percent;
  const [draft, setDraft] = useState<number>(saved ?? 0);
  const [box, setBox] = useState(saved !== null ? String(saved) : '');
  // Only a slider the user actually moved is saved — tabbing past one must not turn a € budget into 0 %.
  const moved = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Follow the saved value, except while the user is still moving this slider.
  useEffect(() => {
    if (moved.current) return;
    setDraft(saved ?? 0);
    setBox(saved !== null ? String(saved) : '');
  }, [saved]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const latest = useRef(draft);
  latest.current = draft;
  const commitSlider = () => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    if (!moved.current) return;
    moved.current = false;
    commit(latest.current);
  };
  /** Arrow keys: save once the keys have been still for half a second, not on every press. */
  const commitSoon = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(commitSlider, 500);
  };
  const commit = (value: number) => {
    const v = Math.min(Math.max(value, 0), 1000);
    if (v !== saved) onSave(v);
  };
  const commitBox = () => {
    const t = box.trim().replace('%', '').replace(',', '.');
    if (t === (saved !== null ? String(saved) : '')) return;
    if (t === '') { if (saved !== null || row.mixed) onSave(null); return; }
    const n = Number(t);
    if (Number.isFinite(n) && n >= 0) commit(n);
    else setBox(saved !== null ? String(saved) : '');
  };
  const status = saved !== null ? null : row.mixed ? 'different % per month' : 'not set — € budget';

  return (
    <li className="grid grid-cols-[9rem_1fr_4.5rem_8.5rem_1.5rem] items-center gap-3" data-testid={`share-row-${row.cat}`}>
      <span className="truncate text-sm">{row.cat}</span>
      <input
        type="range" min={0} max={MAX_PCT} step={0.5}
        aria-label={`${row.cat} % of income`}
        value={Math.min(draft, MAX_PCT)}
        onChange={(e) => { moved.current = true; setDraft(Number(e.target.value)); setBox(e.target.value); }}
        onPointerUp={commitSlider}
        onKeyUp={commitSoon}
        onBlur={commitSlider}
        className={`w-full accent-[rgb(var(--c-secondary))] ${saved === null ? 'opacity-50' : ''}`}
      />
      <span className="flex items-center gap-0.5">
        <input
          inputMode="decimal"
          aria-label={`${row.cat} % exact`}
          value={box}
          placeholder={row.mixed ? 'mixed' : '–'}
          onChange={(e) => setBox(e.target.value)}
          onBlur={commitBox}
          onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
          className="num h-7 w-12 rounded border border-line bg-surface px-1.5 text-right text-xs focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        />
        <span className="text-xs text-ink-muted">%</span>
      </span>
      <span className="num text-right text-xs text-ink-soft" title={status ?? 'The euros across the coming months'}>
        {status ? <span className="text-ink-muted">{status}</span> : <>{money(row.amount)}</>}
      </span>
      {saved !== null || row.mixed ? (
        <button type="button" className="btn-ghost btn-sm px-1" aria-label={`Remove the % from ${row.cat}`}
          title="Back to a plain € budget (the current amounts stay)" onClick={() => onSave(null)}>
          <X size={12} />
        </button>
      ) : <span />}
    </li>
  );
}
