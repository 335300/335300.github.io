import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fmtAxis, fmtMoney, fmtPct } from '../../lib/format';
import { color, useThemeVersion } from '../../lib/theme';
import type { BudgetStatus, Dashboard } from '../../lib/types';
import { TooltipCard } from './ChartTooltip';

type Row = Dashboard['budget_vs_real']['rows'][number];

/** Spent bars wear the reserved status colours; the word always travels with them. */
const STATUS: Record<BudgetStatus, { token: Parameters<typeof color>[0]; alpha?: number; word: string }> = {
  under: { token: 'positive', word: 'Within budget' },
  on_budget: { token: 'positive', word: 'On budget' },
  warning: { token: 'warning', word: 'Heads-up' },
  over: { token: 'negative', word: 'Over budget' },
  unbudgeted: { token: 'ink-soft', alpha: 0.6, word: 'No budget' },
};
const statusFill = (s: BudgetStatus) => color(STATUS[s].token, STATUS[s].alpha ?? 1);
const budgetFill = () => color('track');

const BAR = 14; // bar thickness; budget track, spent bar and budget line share one band
const ROW = 38; // height of one category band

const short = (name: string) => (name.length > 16 ? `${name.slice(0, 15)}…` : name);

/** The budget line: a short dark tick at the end of the budget track, drawn above the spent bar. */
function BudgetLine(props: { x?: number; y?: number; width?: number; height?: number; value?: number | number[] }) {
  const { x = 0, y = 0, width = 0, height = 0 } = props;
  if (width <= 0) return <g />;
  return <line x1={x + width} x2={x + width} y1={y - 4} y2={y + height + 4} stroke={color('ink')} strokeWidth={2} strokeLinecap="round" />;
}

/** Places the spent amount after whichever ends later: the spent bar or the budget line. */
function SpentLabel(props: { x?: number | string; y?: number | string; width?: number | string; height?: number | string; index?: number; rows: Row[]; past: boolean }) {
  const row = props.index !== undefined ? props.rows[props.index] : undefined;
  if (!row || !row.real) return null;
  const spentPastBudget = row.real > row.budget;
  if (spentPastBudget !== props.past) return null;
  const x = Number(props.x ?? 0) + Number(props.width ?? 0) + 7;
  const y = Number(props.y ?? 0) + Number(props.height ?? 0) / 2;
  return <text x={x} y={y} dy="0.35em" fill={color('ink-soft')} fontSize={12} fontWeight={500}>{fmtAxis(row.real)}</text>;
}

/**
 * Budget vs real as horizontal "bullet" bars on one euro scale. For every category
 * a light track runs to the budget (marked by a dark line), and the spent bar is
 * drawn on it, coloured by its status: what is left shows as uncovered track, an
 * overspend runs past the line. Every value, difference and status comes from the
 * backend (services/dashboard.py).
 */
export function BudgetVsRealChart({ rows }: { rows: Row[] }) {
  useThemeVersion();
  const height = rows.length * ROW + 34;
  const present = [...new Set(rows.map((r) => (r.status === 'on_budget' ? 'under' : r.status)))] as BudgetStatus[];
  const order: BudgetStatus[] = ['under', 'warning', 'over', 'unbudgeted'];

  return (
    <div>
      <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-label text-ink-soft" aria-label="Chart legend">
        <li className="flex items-center gap-1.5">
          <span className="relative h-2.5 w-4 rounded-sm" style={{ background: budgetFill() }}>
            <span className="absolute -top-0.5 right-0 h-3.5 w-0.5 rounded" style={{ background: color('ink') }} />
          </span>
          Budget
        </li>
        {order.filter((s) => present.includes(s)).map((s) => (
          <li key={s} className="flex items-center gap-1.5">
            <span className="h-2.5 w-3.5 rounded-sm" style={{ background: statusFill(s) }} /> Spent · {STATUS[s].word.toLowerCase()}
          </li>
        ))}
      </ul>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={rows} layout="vertical" barSize={BAR} barGap={-BAR} barCategoryGap={ROW - BAR}
          margin={{ top: 0, right: 64, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={color('border')} horizontal={false} />
          <XAxis type="number" tickFormatter={fmtAxis} tickLine={false} axisLine={false} tick={{ fill: color('ink-muted'), fontSize: 12 }} />
          <YAxis type="category" dataKey="cat" width={118} tickLine={false} axisLine={{ stroke: color('border') }}
            tickFormatter={short} tick={{ fill: color('ink'), fontSize: 12 }} />
          <Tooltip
            cursor={{ fill: color('neutral-tint') }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const r = payload[0].payload as Row;
              return (
                <TooltipCard
                  title={`${r.cat} · ${STATUS[r.status].word}`}
                  rows={[
                    { label: 'Budget', value: r.budget ? fmtMoney(r.budget) : '—', swatch: budgetFill() },
                    { label: 'Spent', value: fmtMoney(r.real), swatch: statusFill(r.status) },
                    ...(r.budget
                      ? [{ label: r.diff < 0 ? 'Over by' : 'Left', value: fmtMoney(Math.abs(r.diff)) },
                         ...(r.used_pct !== null ? [{ label: 'Used', value: fmtPct(r.used_pct) }] : [])]
                      : []),
                  ]}
                />
              );
            }}
          />
          <Bar name="Budget" dataKey="budget" fill={budgetFill()} radius={[0, 4, 4, 0]} isAnimationActive={false} />
          <Bar name="Spent" dataKey="real" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {rows.map((r) => <Cell key={r.cat} fill={statusFill(r.status)} />)}
            {/* The spent amount, in ink (text never wears the data colour): at the tip of the
                bar when it goes past the budget, otherwise after the budget line (below). */}
            <LabelList dataKey="real" content={(p) => <SpentLabel {...p} rows={rows} past />} />
          </Bar>
          <Bar name="Budget line" dataKey="budget" shape={<BudgetLine />} isAnimationActive={false}>
            <LabelList dataKey="real" content={(p) => <SpentLabel {...p} rows={rows} past={false} />} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
