import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Flag } from 'lucide-react';
import { fmtAxis, fmtDate, fmtMoney, fmtSigned } from '../../lib/format';
import { color, useThemeVersion } from '../../lib/theme';
import type { RollingLine, RollingRow } from '../../lib/types';
import { TooltipCard } from './ChartTooltip';

/** Line colours, in scenario order: most likely = primary, then chart identity colours. Each line is also named in the legend (never colour alone). */
export const LINE_TOKENS = ['primary', 'chart-2', 'chart-5'] as const;

/** A 50 % / 80 % range for one month: [low, high] each. Comes from the backend. */
export interface ForecastBand {
  band50?: [number, number] | null;
  band80?: [number, number] | null;
}
export const lineColor = (i: number, alpha = 1) => color(LINE_TOKENS[i % LINE_TOKENS.length], alpha);

type Point = { label: string; month_name: string; actual: boolean; row: RollingRow } & Record<string, unknown>;

/**
 * The rolling 12-month balance. Recorded months are one solid line; from the
 * last recorded month on, every scenario is its own dashed line. A flag marks
 * each month a savings goal is spent; the dotted "free to use" line is the
 * (first) balance minus what is set aside for goals. Only reshapes backend
 * numbers into chart series — no arithmetic.
 */
export function RollingForecastChart({ rows, lines, bands }: {
  rows: RollingRow[];
  lines: RollingLine[];
  /** Optional ranges for the first scenario, read from each row (the backend fields arrive later). */
  bands?: (row: RollingRow) => ForecastBand | null | undefined;
}) {
  useThemeVersion();
  const lastActual = rows.reduce((idx, r, i) => (r.actual ? i : idx), -1);
  const first = lines[0]?.key;
  const data: Point[] = rows.map((r, i) => {
    const point: Point = { label: r.label, month_name: r.month_name, actual: r.actual, row: r };
    point.recorded = i <= lastActual && first ? r.values[first].balance : null;
    for (const line of lines) point[line.key] = i >= lastActual ? r.values[line.key].balance : null;
    point.free = !r.actual && first ? (r.values[first].free ?? null) : null;
    const band = bands?.(r);
    point.band50 = band?.band50 ?? null;
    point.band80 = band?.band80 ?? null;
    return point;
  });
  const hasNegative = lines.some((l) => l.goes_negative || (l.lowest_free ?? 0) < 0);
  const showFree = data.some((p) => p.free !== null && p.free !== undefined);
  const goalMonths = rows.filter((r) => r.goals && r.goals.length);
  const hasBand50 = data.some((p) => p.band50);
  const hasBand80 = data.some((p) => p.band80);
  const today = lastActual >= 0 ? rows[lastActual] : undefined;
  const axisTick = { fill: color('ink-muted'), fontSize: 12, fontWeight: 500 };

  return (
    <div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data} margin={{ top: 20, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={color('border')} vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: color('border') }} tick={axisTick} />
          <YAxis tickFormatter={fmtAxis} tickLine={false} axisLine={false} width={60} tick={axisTick} />
          {hasNegative && <ReferenceLine y={0} stroke={color('negative')} strokeDasharray="3 3" />}
          {hasBand80 && <Area type="monotone" dataKey="band80" stroke="none" fill={color('band80')} fillOpacity={1} isAnimationActive={false} activeDot={false} />}
          {hasBand50 && <Area type="monotone" dataKey="band50" stroke="none" fill={color('band50')} fillOpacity={1} isAnimationActive={false} activeDot={false} />}
          {today && (
            <ReferenceLine x={today.label} stroke={color('ink-soft')} strokeWidth={1}
              label={{ value: 'Today', position: 'top', fill: color('ink-soft'), fontSize: 12, fontWeight: 600 }} />
          )}
          {goalMonths.map((r) => (
            <ReferenceLine key={`goal-${r.key}`} x={r.label} stroke={color('positive', 0.55)} strokeDasharray="2 3"
              label={<GoalFlag names={r.goals!.map((g) => g.name)} />} />
          ))}
          <Tooltip
            cursor={{ stroke: color('border') }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as Point;
              const v0 = first ? p.row.values[first] : undefined;
              if (!v0) return null;
              return (
                <TooltipCard
                  title={`${p.month_name} · ${p.actual ? 'recorded' : 'planned'}`}
                  rows={[
                    ...(p.actual
                      ? [{ label: 'Balance', value: fmtMoney(v0.balance), swatch: color('ink') }]
                      : lines.map((l, i) => ({
                          label: lines.length > 1 ? `Balance · ${l.name}` : 'Balance',
                          value: fmtMoney(p.row.values[l.key].balance),
                          swatch: lineColor(i),
                          dashed: true,
                        }))),
                    { label: 'Cash in', value: fmtMoney(v0.income) },
                    { label: 'Costs', value: fmtMoney(v0.expenses) },
                    ...(v0.invested ? [{ label: 'Invested', value: fmtMoney(v0.invested) }] : []),
                    { label: 'Kept this month', value: fmtSigned(v0.savings) },
                    ...(p.row.goals ?? []).map((g) => ({
                      label: `Goal bought: ${g.name}${g.overdue ? ' (date passed)' : ''}`,
                      value: `−${fmtMoney(g.amount)}`,
                      swatch: color('positive'),
                    })),
                    ...(v0.free !== undefined && v0.free !== null && !p.actual
                      ? [{ label: 'Free to use (after goal savings)', value: fmtMoney(v0.free), swatch: color('secondary'), dashed: true }]
                      : []),
                    ...(lines.length > 1 && !p.actual ? [{ label: `(figures for ${lines[0].name})`, value: '' }] : []),
                  ]}
                />
              );
            }}
          />
          <Line type="monotone" dataKey="recorded" stroke={color('ink')} strokeWidth={2} dot={false}
            connectNulls={false} isAnimationActive={false} activeDot={{ r: 5 }} />
          {showFree && (
            <Line type="monotone" dataKey="free" name="Free to use" stroke={color('secondary', 0.85)} strokeWidth={1.75}
              strokeDasharray="2 4" connectNulls={false} isAnimationActive={false} dot={false} activeDot={{ r: 4 }} />
          )}
          {lines.map((l, i) => (
            <Line key={l.key} type="monotone" dataKey={l.key} name={l.name} stroke={lineColor(i)} strokeWidth={2}
              strokeDasharray="6 4" connectNulls={false} isAnimationActive={false} activeDot={{ r: 5 }}
              dot={(props) => <NegativeDot key={`${l.key}-${props.index}`} {...props} />} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-label text-ink-soft" aria-label="Chart legend">
        <li className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-4" style={{ background: color('ink') }} aria-hidden /> Recorded</li>
        {lines.map((l, i) => (
          <li key={l.key} className="flex items-center gap-1.5">
            <span className="inline-block w-4" style={{ borderTop: `2px dashed ${lineColor(i)}` }} />
            {l.name}{l.job_end ? ` (student job ends ${fmtDate(l.job_end)})` : ''}
          </li>
        ))}
        {showFree && (
          <li className="flex items-center gap-1.5">
            <span className="inline-block w-4" style={{ borderTop: `2px dotted ${color('secondary')}` }} />
            Free to use{lines.length > 1 ? ` (${lines[0].name})` : ''} — balance minus money set aside for goals
          </li>
        )}
        {hasBand50 && (
          <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: color('band50') }} aria-hidden /> 50% range</li>
        )}
        {hasBand80 && (
          <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: color('band80') }} aria-hidden /> 80% range</li>
        )}
        {goalMonths.length > 0 && (
          <li className="flex items-center gap-1.5"><Flag size={14} aria-hidden style={{ color: color('positive') }} /> A goal is bought (the money leaves the account)</li>
        )}
      </ul>
    </div>
  );
}

function NegativeDot(props: { cx?: number; cy?: number; value?: number | null }) {
  const { cx, cy, value } = props;
  if (cx == null || cy == null || value == null || value >= 0) return <g />;
  return <circle cx={cx} cy={cy} r={5} fill={color('negative')} stroke={color('surface')} strokeWidth={2} />;
}

/** The flag above a month in which goals are bought: icon plus the goal names. */
function GoalFlag(props: { viewBox?: { x?: number; y?: number }; names: string[] }) {
  const x = props.viewBox?.x ?? 0;
  const y = (props.viewBox?.y ?? 0) + 2;
  const text = props.names.length > 2 ? `${props.names[0]} +${props.names.length - 1}` : props.names.join(' · ');
  return (
    <g transform={`translate(${x},${y})`} aria-label={`Goals bought: ${props.names.join(', ')}`}>
      <path d="M0 0 V14 M0 1 H8 L6 4 L8 7 H0" fill={color('positive', 0.25)} stroke={color('positive')} strokeWidth={1.25} />
      <text x={10} y={9} fontSize={12} fontWeight={500} fill={color('ink-soft')}>{text}</text>
    </g>
  );
}
