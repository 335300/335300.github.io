import { Area, CartesianGrid, ComposedChart, Customized, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fmtAxis, fmtMoney, fmtSigned } from '../../lib/format';
import { color, useThemeVersion } from '../../lib/theme';
import type { ProjectionRow } from '../../lib/types';
import { TooltipCard } from './ChartTooltip';

/** One month on the forecast chart. Every number comes from the backend; the chart only draws it. */
export interface ForecastPoint {
  /** X-axis label ("Nov"). Must be unique. */
  label: string;
  /** Tooltip title ("November 2026"); defaults to `label`. */
  title?: string;
  /** Recorded balance (solid ink line). */
  actual?: number | null;
  /** Most likely balance (dashed primary line). */
  likely?: number | null;
  /** 50 % range [low, high] — the likely half of outcomes. Optional. */
  band50?: [number, number] | null;
  /** 80 % range [low, high] — 8 of 10 likely futures. Optional. */
  band80?: [number, number] | null;
  /** Marks a month where the balance goes below zero (red dot). */
  negative?: boolean;
  /** Extra tooltip lines, already formatted ("Cash in", "€2,100.00"). */
  details?: { label: string; value: string }[];
}

interface Props {
  /** The months to draw (preferred). */
  points?: ForecastPoint[];
  /** Older shape: the projection rows (used when `points` is not given). */
  rows?: ProjectionRow[];
  /** Label of the "Today" month; defaults to the last month with a recorded balance. */
  todayLabel?: string;
  height?: number;
  /** Words after the last most-likely value at the right edge ("likely"). Set null to hide. */
  likelyWord?: string | null;
}

type Datum = ForecastPoint & { likelyLine: number | null };

/** Turns the older projection rows into points (reshaping only, no arithmetic). */
function fromRows(rows: ProjectionRow[]): ForecastPoint[] {
  return rows.map((r) => ({
    label: r.month_short,
    title: `${r.month_name} · ${r.actual ? 'recorded' : 'planned'}`,
    actual: r.actual ? r.balance : null,
    likely: r.actual ? null : r.balance,
    negative: r.negative,
    details: [
      { label: 'Cash in', value: fmtMoney(r.income) },
      { label: 'Costs', value: fmtMoney(r.expenses) },
      ...(r.invested ? [{ label: 'Invested', value: fmtMoney(r.invested) }] : []),
      { label: 'Kept this month', value: fmtSigned(r.savings) },
    ],
  }));
}

/**
 * The balance over time (Style Guide 10): solid ink = recorded, dashed primary
 * = most likely, shaded bands = 50 % and 80 % of likely futures (only when the
 * backend sends them), a "Today" line between the two.
 */
export function ForecastChart({ points, rows = [], todayLabel, height = 260, likelyWord = 'likely' }: Props) {
  useThemeVersion();
  const source = points ?? fromRows(rows);
  const todayIdx = todayLabel !== undefined
    ? source.findIndex((p) => p.label === todayLabel)
    : source.reduce((idx, p, i) => (p.actual !== null && p.actual !== undefined ? i : idx), -1);
  // The dashed line starts at today's recorded value so the two lines meet (same number, no maths).
  const data: Datum[] = source.map((p, i) => ({
    ...p,
    likelyLine: p.likely ?? (i === todayIdx && p.actual !== undefined ? p.actual : null),
  }));
  const today = todayIdx >= 0 ? data[todayIdx] : undefined;
  const last = data[data.length - 1];
  const hasBands = data.some((p) => p.band50 || p.band80);
  const hasNegative = data.some((p) => p.negative);
  const ink = color('ink');
  const primary = color('primary');
  const axisTick = { fill: color('ink-muted'), fontSize: 12, fontWeight: 500 };
  const endLabels = Boolean(likelyWord) && last && last.likelyLine !== null;

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 20, right: endLabels || hasBands ? 104 : 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={color('border')} vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: color('border') }} tick={axisTick} />
          <YAxis tickFormatter={fmtAxis} tickLine={false} axisLine={false} width={60} tick={axisTick} />
          {hasNegative && <ReferenceLine y={0} stroke={color('negative')} strokeDasharray="3 3" />}
          <Tooltip
            cursor={{ stroke: color('border-strong') }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as Datum;
              return (
                <TooltipCard
                  title={p.title ?? p.label}
                  rows={[
                    ...(p.actual !== null && p.actual !== undefined ? [{ label: 'Balance', value: fmtMoney(p.actual), swatch: ink }] : []),
                    ...(p.likely !== null && p.likely !== undefined ? [{ label: 'Most likely', value: fmtMoney(p.likely), swatch: primary, dashed: true }] : []),
                    ...(p.band50 ? [{ label: '50% range', value: `${fmtMoney(p.band50[0], { round: true })} – ${fmtMoney(p.band50[1], { round: true })}`, swatch: color('band50', 2) }] : []),
                    ...(p.band80 ? [{ label: '80% range', value: `${fmtMoney(p.band80[0], { round: true })} – ${fmtMoney(p.band80[1], { round: true })}`, swatch: color('band80', 2) }] : []),
                    ...(p.details ?? []),
                  ]}
                />
              );
            }}
          />
          {hasBands && <Area type="linear" dataKey="band80" stroke="none" fill={color('band80')} fillOpacity={1} isAnimationActive={false} activeDot={false} connectNulls={false} />}
          {hasBands && <Area type="linear" dataKey="band50" stroke="none" fill={color('band50')} fillOpacity={1} isAnimationActive={false} activeDot={false} connectNulls={false} />}
          {today && (
            <ReferenceLine x={today.label} stroke={color('ink-soft')} strokeWidth={1} label={TodayLabel} />
          )}
          <Line type="linear" dataKey="actual" stroke={ink} strokeWidth={2} strokeLinejoin="round" connectNulls={false}
            isAnimationActive={false} dot={(props) => <BalanceDot key={`a-${props.index}`} {...props} todayIdx={todayIdx} />} activeDot={{ r: 4 }} />
          <Line type="linear" dataKey="likelyLine" stroke={primary} strokeWidth={2} strokeDasharray="6 4" connectNulls={false}
            isAnimationActive={false} dot={(props) => <BalanceDot key={`l-${props.index}`} {...props} todayIdx={-1} />} activeDot={{ r: 4 }} />
          {(endLabels || last?.band50 || last?.band80) && last && (
            <Customized component={(chart: ChartGeometry) => <EndLabels chart={chart} label={last.label} items={[
              ...(last.band80 ? [{ key: 'b80', value: last.band80[1], text: '80% range', fill: color('ink-soft'), weight: 500 }] : []),
              ...(last.band50 ? [{ key: 'b50', value: last.band50[1], text: '50% range', fill: color('ink-soft'), weight: 500 }] : []),
              ...(endLabels ? [{ key: 'likely', value: last.likelyLine as number, text: `${fmtMoney(last.likelyLine as number, { round: true })} ${likelyWord}`, fill: primary, weight: 600 }] : []),
            ]} />} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-label text-ink-soft" aria-label="Chart legend">
        <li className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-4" style={{ background: ink }} aria-hidden /> Recorded</li>
        <li className="flex items-center gap-1.5"><span className="inline-block w-4" style={{ borderTop: `2px dashed ${primary}` }} aria-hidden /> Most likely</li>
        {data.some((p) => p.band50) && (
          <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: color('band50') }} aria-hidden /> 50% range</li>
        )}
        {data.some((p) => p.band80) && (
          <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: color('band80') }} aria-hidden /> 80% range</li>
        )}
      </ul>
    </div>
  );
}

/** "Today" above the plot, written to the right of its line so it never sits on the y-axis labels. */
function TodayLabel(props: { viewBox?: { x?: number; y?: number } }) {
  const x = props.viewBox?.x ?? 0;
  const y = props.viewBox?.y ?? 0;
  return (
    <text x={x + 4} y={y - 6} textAnchor="start" fill={color('ink-soft')} fontSize={12} fontWeight={600}>Today</text>
  );
}

/** What Recharts hands a <Customized> part: the axes' scales (screen positions only). */
type ChartGeometry = {
  xAxisMap?: Record<string, { scale: ((v: string) => number | undefined) & { bandwidth?: () => number } }>;
  yAxisMap?: Record<string, { scale: (v: number) => number }>;
};

const LABEL_GAP = 15; // px between two right-edge labels

/**
 * The words at the right edge ("80% range", "50% range", "1.234 € likely"), each next to
 * its own value. When the bands are narrow the words would sit on top of each other, so
 * each one is pushed down until it clears the one above (screen pixels only).
 */
function EndLabels({ chart, label, items }: {
  chart: ChartGeometry;
  label: string;
  items: { key: string; value: number; text: string; fill: string; weight: number }[];
}) {
  const xAxis = Object.values(chart.xAxisMap ?? {})[0];
  const yAxis = Object.values(chart.yAxisMap ?? {})[0];
  if (!xAxis || !yAxis) return null;
  const x0 = xAxis.scale(label);
  if (x0 === undefined) return null;
  const x = x0 + (xAxis.scale.bandwidth?.() ?? 0) / 2 + 10;
  const placed = items
    .map((it) => ({ ...it, y: yAxis.scale(it.value) }))
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < placed.length; i++) {
    if (placed[i].y < placed[i - 1].y + LABEL_GAP) placed[i].y = placed[i - 1].y + LABEL_GAP;
  }
  return (
    <g>
      {placed.map((it) => (
        <text key={it.key} x={x} y={it.y} dominantBaseline="central" fill={it.fill} fontSize={12} fontWeight={it.weight}>{it.text}</text>
      ))}
    </g>
  );
}

/** Today's point gets a hollow ring; a month below zero gets a red dot. */
function BalanceDot(props: { cx?: number; cy?: number; index?: number; payload?: Datum; value?: number | null; todayIdx: number }) {
  const { cx, cy, payload, value, index, todayIdx } = props;
  if (cx == null || cy == null || value == null) return <g />;
  if (payload?.negative) return <circle cx={cx} cy={cy} r={5} fill={color('negative')} stroke={color('surface')} strokeWidth={2} />;
  if (index === todayIdx) return <circle cx={cx} cy={cy} r={4} fill={color('surface')} stroke={color('ink')} strokeWidth={2} />;
  return <g />;
}
