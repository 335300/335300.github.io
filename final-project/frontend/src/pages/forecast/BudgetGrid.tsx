import { ArrowDown, ArrowUp, CalendarDays, Landmark, RotateCcw, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useBudgets, useSetBudget, useSetRowShare } from '../../api/queries';
import { EmptyState } from '../../components/ui/Card';
import { CategoryDot } from '../../components/ui/CategoryDot';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { fmtMoney, fmtSigned, MONTHS_SHORT, parseAmount } from '../../lib/format';
import type { Budgets, BudgetGrid as Grid, BudgetGridRow, KindTotal, TxType } from '../../lib/types';
import { AllocationPanel, fmtShare, JOB_COLOUR } from './AllocationPanel';
import { VariableSharePanel } from './VariableSharePanel';

/** € = cells show and take euros; % = cost cells show and take a % of the month's planned income. */
export type BudgetMode = 'eur' | 'pct';
type Mode = BudgetMode;

/** A budget typed in euros, linked to a % of the month's planned income (converted by the backend),
 * or a box typed over a figure that fills itself set back to automatic. */
type Amount = { value: number } | { percent: number } | { auto: true };

/** What every row needs to know about the table around it. */
interface Ctx {
  mode: Mode;
  lastActual: number | null;
  links: Budgets['links'];
  onSave: (kind: TxType, cat: string, month: number, amount: Amount) => void;
  onRowShare: (cat: string, percent: number | null) => void;
}

const MODE_KEY = 'pc-budget-mode';
const readMode = (): Mode => {
  try { return localStorage.getItem(MODE_KEY) === 'pct' ? 'pct' : 'eur'; } catch { return 'eur'; }
};

/** Euros or share of income — remembered per viewer. The page puts the switch in the card header. */
export function useBudgetMode(): [Mode, (m: Mode) => void] {
  const [mode, setModeState] = useState<Mode>(readMode);
  const setMode = (m: Mode) => {
    setModeState(m);
    try { localStorage.setItem(MODE_KEY, m); } catch { /* per-viewer convenience only */ }
  };
  return [mode, setMode];
}

/** The "Euros | Share of income" switch (segmented control). */
export function BudgetModeToggle({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <div className="flex gap-0.5 rounded-lg bg-neutral-tint p-[3px]" role="radiogroup" aria-label="Show budgets as">
      {([['eur', 'Euros'], ['pct', 'Share of income']] as const).map(([m, word]) => (
        <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => onChange(m)}
          className={`h-[26px] rounded-input px-2.5 text-[13px] ${mode === m ? 'bg-surface font-semibold text-ink shadow-tab' : 'font-medium text-ink-soft hover:text-ink'}`}>
          {word}
        </button>
      ))}
    </div>
  );
}

/**
 * The 12-month budget plan. Lives on the Forecast tab because changing a budget
 * is a planning decision — its effect on the forecast and goals shows right here.
 */
export function BudgetGrid({ year, lastActual, simple = false, mode: modeProp = 'eur' }: {
  year: number;
  lastActual: number | null;
  /** The Joint plan: euros only — no % view, no income-split panels or rows. */
  simple?: boolean;
  /** Euros or share of income (from useBudgetMode; the switch sits in the card header). */
  mode?: Mode;
}) {
  const { data, isLoading, error } = useBudgets(year);
  const save = useSetBudget(year);
  const rowShare = useSetRowShare(year);
  const mode: Mode = simple ? 'eur' : modeProp;
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error} />;

  const fixed = data.expense.rows.filter((r) => r.kind === 'fixed');
  const variable = data.expense.rows.filter((r) => r.kind === 'variable');
  const invest = data.expense.rows.filter((r) => r.kind === 'investment');
  const ctx: Ctx = {
    mode,
    lastActual,
    links: data.links ?? { salary_category: null, calendar_months: Array(12).fill(false), open_months: [] },
    onSave: (kind, cat, month, amount) => save.mutate({ kind, cat, month, ...amount }),
    onRowShare: (cat, percent) => rowShare.mutate({ cat, percent }),
  };
  // The Joint plan usually has no investments: then "All cash out" closes the variable costs.
  const showInvest = !simple || invest.length > 0;

  if (!data.expense.rows.length && !data.income.rows.length) {
    return <EmptyState title="No categories yet">Add categories in the Transactions tab, then plan them here.</EmptyState>;
  }

  return (
    <div>
      {simple && (
        <p className="mb-2 px-5 text-xs text-ink-soft">
          Amounts in euros. Type a number and press Tab or click away to save. <span className="italic">Grey italic cells</span> fill
          themselves in.
        </p>
      )}
      <div className="overflow-x-auto px-5">
        <table className="w-full min-w-[1180px] text-[13px]">
          <thead>
            <tr className="border-b border-line-strong text-label text-ink-soft">
              <th className="sticky left-0 z-[1] w-40 bg-surface py-2 text-left">Category</th>
              {MONTHS_SHORT.map((m, i) => (
                <th key={m} className={`py-2 pr-1.5 text-right ${lastActual !== null && i <= lastActual ? 'text-ink-muted' : ''}`}
                  title={lastActual !== null && i <= lastActual ? 'Recorded month' : undefined}>{m}</th>
              ))}
              <th className="py-2 pl-2 text-right">{mode === 'pct' ? 'Year · %' : 'Year'}</th>
            </tr>
          </thead>
          <tbody>
            <Section label="Income" rows={data.income.rows} kind="income" grid={data.income} ctx={ctx} />
            <Section label="Fixed costs" rows={fixed} kind="expense" ctx={ctx} subtotal={data.expense.kind_totals?.fixed} />
            <Section label="Variable costs" rows={variable} kind="expense" ctx={ctx} subtotal={data.expense.kind_totals?.variable}
              grid={showInvest ? undefined : data.expense} totalLabel={showInvest ? undefined : 'All cash out'} />
            {showInvest && (
              <Section label="Investments" rows={invest} kind="expense" grid={data.expense} ctx={ctx} totalLabel="All cash out"
                subtotal={data.expense.kind_totals?.investment}
                emptyHint="No investment category yet. Add one in the Transactions tab (Categories → type “Investment”), then plan it here." />
            )}
            <SavedSection saved={data.saved} />
            {!simple && data.allocation && <ShareSection allocation={data.allocation} />}
          </tbody>
        </table>
      </div>
      {!simple && (data.allocation || data.links?.panel) && (
        <div className="mt-5 space-y-4 border-t border-line px-5 pt-5">
          {data.allocation && <AllocationPanel allocation={data.allocation} lastActual={lastActual} />}
          {data.links?.panel && <VariableSharePanel year={year} panel={data.links.panel} />}
        </div>
      )}
      {simple && (
        <p className="mt-2 px-5 text-xs text-ink-soft">
          Greyed months are already recorded. The “From …” rows follow the plan: each of us pays in our part of the costs and of
          the goal savings — so “Planned kept” is the money that goes to our goals.
        </p>
      )}
      <div className="px-5"><ErrorNote error={save.error || rowShare.error} /></div>
    </div>
  );
}

function Section({ label, rows, kind, grid, ctx, totalLabel, subtotal, emptyHint }: {
  label: string;
  rows: BudgetGridRow[];
  kind: TxType;
  grid?: Grid;
  ctx: Ctx;
  totalLabel?: string;
  /** The section's own sum (e.g. all fixed costs), from the backend. */
  subtotal?: KindTotal;
  /** Shown instead of rows when the section has no category yet. */
  emptyHint?: string;
}) {
  return (
    <>
      <tr>
        <td colSpan={14} className="h-7 border-b border-line bg-bg px-1 text-label text-ink-soft">{label}</td>
      </tr>
      {rows.length === 0 && emptyHint && (
        <tr className="border-t border-line/60">
          <td colSpan={14} className="py-2 text-xs text-ink-muted">{emptyHint}</td>
        </tr>
      )}
      {rows.map((r) => {
        const fromCalendar = kind === 'income' && r.cat === ctx.links.salary_category;
        const planFlags = kind === 'expense' ? ctx.links.plan_months?.[r.cat] : undefined;
        const plan = planFlags ? ctx.links.plans?.[r.cat] : undefined;
        const joint = ctx.links.joint;
        const jointRow = joint?.[kind]?.[r.cat];
        // A box that fills itself: what fills it (the box can still be typed over).
        const source = (m: number) =>
          fromCalendar && ctx.links.calendar_months[m]
            ? 'the income calendar (the net pay expected to arrive this month)'
            : plan && planFlags?.[m]
              ? `the investment plan “${plan.name}” (one ${plan.unit} a month at about ${fmtMoney(plan.cost ?? 0)})`
              : jointRow?.months[m]
                ? joint?.role === 'joint'
                  ? `our plan (${jointRow.name}’s part of this month’s costs and goal savings)`
                  : `the Joint plan (${jointRow.name}’s part of the shared costs and goal savings)`
                : null;
        return (
          <tr key={r.cat} className="border-b border-line">
            <td className="sticky left-0 z-[1] max-w-[160px] truncate bg-surface py-1 pr-2">
              <span className="flex items-center gap-1">
                <CategoryDot cat={r.cat} kind={r.kind} income={kind === 'income'} className="mr-1" />
                <span className="truncate">{r.cat}</span>
                {fromCalendar && ctx.links.calendar_months.some(Boolean) && (
                  <CalendarDays size={12} className="shrink-0 text-ink-muted" aria-label="follows the income calendar" />
                )}
                {plan && planFlags?.some(Boolean) && (
                  <Landmark size={12} className="shrink-0 text-invest" aria-label={`follows the investment plan ${plan.name}`} />
                )}
                {jointRow?.months.some(Boolean) && (
                  <Users size={12} className="shrink-0 text-secondary" aria-label="follows the Joint plan" />
                )}
              </span>
            </td>
            {r.values.map((v, m) => (
              <td key={m} className="py-1 pl-1">
                <Cell value={v} actual={r.actuals[m]} recorded={ctx.lastActual !== null && m <= ctx.lastActual}
                  share={r.shares?.[m] ?? null} link={r.links?.[m] ?? null} kind={kind} mode={ctx.mode}
                  source={source(m)} typed={r.manual?.[m] ?? false}
                  label={`${r.cat} budget ${MONTHS_SHORT[m]}`} onSave={(amount) => ctx.onSave(kind, r.cat, m, amount)} />
              </td>
            ))}
            <td className="num py-1 pl-2 text-right font-medium">
              {kind === 'expense' && ctx.mode === 'pct'
                ? <RowShare row={r} open={ctx.links.open_months} onSave={(p) => ctx.onRowShare(r.cat, p)} />
                : fmtMoney(r.total, { round: true })}
            </td>
          </tr>
        );
      })}
      {subtotal && rows.length > 0 && (
        <tr className="border-b border-line font-medium text-ink-soft" data-testid={`subtotal-${label.toLowerCase().replace(' ', '-')}`}>
          <td className="sticky left-0 z-[1] bg-surface py-1.5 pl-1">All {label.toLowerCase()}</td>
          {subtotal.monthly.map((t, m) => (
            <td key={m} className="num py-1.5 pr-1.5 text-right">{fmtMoney(t, { round: true })}</td>
          ))}
          <td className="num py-1.5 pl-2 text-right font-semibold">{fmtMoney(subtotal.total, { round: true })}</td>
        </tr>
      )}
      {grid && (
        <tr className="border-b border-line-strong font-semibold">
          <td className="sticky left-0 z-[1] bg-surface py-1.5">{totalLabel ?? `All ${label.toLowerCase()}`}</td>
          {grid.monthly_totals.map((t, m) => (
            <td key={m} className="num py-1.5 pr-1.5 text-right">{fmtMoney(t, { round: true })}</td>
          ))}
          <td className="num py-1.5 pl-2 text-right">{fmtMoney(grid.grand_total, { round: true })}</td>
        </tr>
      )}
    </>
  );
}

/** "12.5" — a stored % without trailing zeros, for an input box. */
const pctText = (v: number) => String(Number(v.toFixed(2)));

function Cell({ value, actual, recorded, share, link, kind, mode, source, typed, label, onSave }: {
  value: number;
  actual: number;
  recorded: boolean;
  /** This budget as a % of the month's planned income, from the backend. */
  share: number | null;
  /** The % this cell is linked to, or null. */
  link: number | null;
  kind: TxType;
  mode: Mode;
  /** What fills this box by itself (the income calendar, an investment plan, the Joint plan), or null. */
  source: string | null;
  /** Typed by hand over a figure that fills itself (the automatic fill leaves it alone). */
  typed: boolean;
  label: string;
  onSave: (amount: Amount) => void;
}) {
  const auto = source !== null && !typed;
  // A box that fills itself, or one typed over it, takes euros only.
  const asPct = mode === 'pct' && kind === 'expense' && source === null && !typed;
  const shown = asPct ? (link !== null ? pctText(link) : '') : value ? String(value) : '';
  const [text, setText] = useState(shown);
  useEffect(() => setText(shown), [shown]);

  const trimmed = text.trim();
  const typedPct = kind === 'expense' && (asPct || trimmed.endsWith('%'));
  const parsed = parseAmount((trimmed.endsWith('%') ? trimmed.slice(0, -1) : trimmed) || '0');
  const invalid = parsed === null || parsed < 0 || (trimmed.includes('%') && !trimmed.endsWith('%')) || (trimmed.endsWith('%') && kind !== 'expense');

  const commit = () => {
    if (invalid || ((source !== null || typed) && typedPct)) {
      setText(shown);
      return;
    }
    if (trimmed === shown) return;
    if (asPct && trimmed === '') onSave({ value: 0 });          // clearing a % removes the link and the budget
    else if (typedPct) {
      setText(shown); // the backend's answer replaces it
      onSave({ percent: parsed! });
    } else if (parsed !== value) onSave({ value: parsed! });
  };

  const hints = [
    auto ? `Fills itself from ${source} · type to set it by hand` : null,
    typed ? 'Typed by hand · ↺ follows the automatic figure again' : null,
    recorded ? `Recorded: ${fmtMoney(actual)}` : null,
    link !== null ? `${fmtMoney(value)} — follows ${fmtShare(link)} of this month’s planned income` : null,
    link === null && value && share !== null ? `${fmtShare(share)} of planned income` : null,
  ].filter(Boolean);
  // In % view an unlinked cost shows its current share faintly, so you see where you start from.
  const placeholder = asPct ? (value && share !== null ? `${pctText(share)}` : '%') : '0';

  return (
    <div className="relative">
      {/* The unit of the view: € for amounts, % for shares of income. */}
      {typed && (
        <button type="button" aria-label={`Back to automatic: ${label}`} title="Typed by hand — back to the automatic figure"
          className="absolute left-0 top-1/2 z-10 -translate-y-1/2 rounded p-1 text-primary hover:bg-primary-tint focus:outline-none focus:ring-2 focus:ring-primary/30"
          onClick={() => onSave({ auto: true })}>
          <RotateCcw size={12} />
        </button>
      )}
      {(value !== 0 || link !== null || asPct) && !auto && !typed && (
        <span className={`pointer-events-none absolute left-1 top-1/2 -translate-y-1/2 text-xs ${link !== null ? 'font-semibold text-secondary' : 'text-ink-muted/70'}`} aria-hidden>
          {asPct ? '%' : '€'}
        </span>
      )}
      <input
        aria-label={label}
        title={hints.length ? hints.join(' · ') : undefined}
        inputMode="decimal"
        value={text}
        data-typed={typed ? 'true' : undefined}
        placeholder={placeholder}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
        data-linked={link !== null ? 'true' : undefined}
        className={`num h-7 w-full rounded-input border px-1.5 text-right text-[13px] focus:border-primary focus:outline-none focus:ring-2 focus:ring-focus-ring ${
          invalid ? 'border-negative' : 'border-transparent hover:border-line-strong'
        } ${auto ? 'bg-transparent italic text-ink-soft' : typed ? 'bg-neutral-tint pl-5 font-medium text-ink' : recorded ? 'bg-transparent text-ink-soft' : 'bg-transparent text-ink'} ${
          link !== null ? 'font-medium text-secondary' : ''
        } ${asPct && link === null ? 'placeholder:text-ink-muted/60' : ''}`}
      />
    </div>
  );
}

/** The Year box in % view: one % for every month not recorded yet. */
function RowShare({ row, open, onSave }: { row: BudgetGridRow; open: number[]; onSave: (percent: number | null) => void }) {
  const values = open.map((m) => row.links?.[m] ?? null);
  const common = values.length && values.every((v) => v !== null && v === values[0]) ? values[0] : null;
  const mixed = common === null && values.some((v) => v !== null);
  const shown = common !== null ? pctText(common) : '';
  const [text, setText] = useState(shown);
  useEffect(() => setText(shown), [shown]);
  const trimmed = text.trim().replace(/%$/, '');
  const parsed = trimmed ? parseAmount(trimmed) : null;
  const invalid = trimmed !== '' && (parsed === null || parsed < 0);

  const commit = () => {
    if (invalid) { setText(shown); return; }
    if (text.trim() === shown) return;
    if (trimmed === '') { if (common !== null || mixed) onSave(null); return; }
    onSave(parsed);
  };

  if (!open.length) return <span className="text-ink-muted" title="Every month is recorded">–</span>;
  return (
    <input
      aria-label={`${row.cat} % for all open months`}
      title={`One % of planned income for every month from ${MONTHS_SHORT[open[0]]} on. Empty removes the links (the euros stay).`}
      inputMode="decimal"
      value={text}
      placeholder={mixed ? 'mixed' : '%'}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
      className={`num h-7 w-16 rounded border px-1.5 text-right text-xs font-medium focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 ${
        invalid ? 'border-negative' : 'border-line'
      } bg-primary-tint/40`}
    />
  );
}

/** Planned vs actually saved per month. Every figure comes from the backend. */
function SavedSection({ saved }: { saved: Budgets['saved'] }) {
  const tone = (v: number) => (v < 0 ? 'text-negative' : v > 0 ? 'text-positive' : 'text-ink-soft');
  const cell = (v: number) => fmtSigned(v, { round: true });
  return (
    <>
      <tr className="border-y border-line-strong font-semibold" data-testid="planned-kept">
        <td className="sticky left-0 z-[1] bg-surface py-2">Planned kept</td>
                {saved.planned.map((v, m) => (
          <td key={m} className={`num py-2 pr-1.5 text-right ${tone(v)}`}>{cell(v)}</td>
        ))}
        <td className={`num py-1.5 pl-2 text-right font-semibold ${tone(saved.planned_total)}`}>{cell(saved.planned_total)}</td>
      </tr>
      <tr className="border-b border-line">
        <td className="sticky left-0 z-[1] bg-surface py-1.5">Actually kept</td>
                {saved.actual.map((v, m) => (
          <td key={m} className={`num py-1.5 pr-1.5 text-right ${v === null ? 'text-ink-muted' : tone(v)}`}>
            {v === null ? <span aria-label="not recorded">–</span> : cell(v)}
          </td>
        ))}
        <td className={`num py-1.5 pl-2 text-right font-semibold ${tone(saved.actual_total)}`}>{cell(saved.actual_total)}</td>
      </tr>
    </>
  );
}

/** Each job's share of the month's planned income, under the month it belongs to. */
function ShareSection({ allocation }: { allocation: Budgets['allocation'] }) {
  const keys = ['fixed', 'variable', 'investment', 'savings'] as const;
  const label = { fixed: 'Fixed costs', variable: 'Variable costs', investment: 'Investments', savings: 'Savings' };
  const cell = (split: Budgets['allocation']['year'], key: (typeof keys)[number]) => {
    const b = split.blocks.find((x) => x.key === key)!;
    if (!split.income) return <span className="text-ink-muted" aria-label="no income planned">–</span>;
    const Arrow = b.status === 'above' ? ArrowUp : ArrowDown;
    return (
      <span className={`inline-flex items-center justify-end gap-0.5 ${b.attention ? 'text-warning' : b.share < 0 ? 'text-negative' : ''}`}
        title={`${b.label}: ${fmtMoney(b.amount)} · ${fmtShare(b.share)} of planned income`}>
        {b.attention && <Arrow size={11} aria-label={b.status === 'above' ? 'above the guide' : 'below the guide'} />}
        {fmtShare(b.share)}
      </span>
    );
  };
  return (
    <>
      <tr>
        <td colSpan={14} className="h-7 border-b border-line bg-bg px-1 text-label text-ink-soft">Share of planned income</td>
      </tr>
      {keys.map((key) => (
        <tr key={key} className="border-b border-line" data-testid={`share-${key}`}>
          <td className="sticky left-0 z-[1] bg-surface py-1.5">
            <span className="flex items-center gap-1.5">
              <span className={`h-2 w-2 shrink-0 rounded-sm ${JOB_COLOUR[key]}`} aria-hidden />
              {label[key]}
            </span>
          </td>
          {allocation.months.map((m) => (
            <td key={m.month} className="num py-1.5 pr-1.5 text-right">{cell(m, key)}</td>
          ))}
          <td className="num py-1.5 pl-2 text-right font-semibold">{cell(allocation.year, key)}</td>
        </tr>
      ))}
    </>
  );
}
