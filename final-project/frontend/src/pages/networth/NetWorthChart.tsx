import { Bar, CartesianGrid, Cell, ComposedChart, LabelList, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { TooltipCard } from '../../components/charts/ChartTooltip';
import { fmtAxis, fmtMoney } from '../../lib/format';
import { color, useThemeVersion } from '../../lib/theme';
import type { NetWorthPoint } from '../../lib/types';

/** Why a month is only an estimate, in words (reasons come from services/net_worth_history.py). */
export const REASON_WORD: Record<NetWorthPoint['estimated_reasons'][number], string> = {
  carried_back: 'an account had no value yet, so its first value was used',
  rate: 'no exchange rate yet, so the first one was used',
  plan_before_added: 'before the land plan was added',
  land_value: 'the land value is only known for today',
  not_recorded: 'no transactions recorded for this month',
};

const STRIPES = 'nw-estimated-stripes';
const STRIPES_PALE = 'nw-estimated-stripes-pale';

/** Diagonal stripes = estimated month. A pattern, not only a colour, plus the word under the bar. */
function Stripes({ id, fill, stripe }: { id: string; fill: string; stripe: string }) {
  return (
    <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill={fill} />
      <line x1="0" y1="0" x2="0" y2="6" stroke={stripe} strokeWidth="3" />
    </pattern>
  );
}

/** A small legend swatch drawn in SVG so it can show the same stripes as the bars. */
function Swatch({ fill, stroke, pattern }: { fill: string; stroke?: string; pattern?: { id: string; fill: string; stripe: string } }) {
  return (
    <svg width="14" height="10" aria-hidden>
      {pattern && <defs><Stripes {...pattern} /></defs>}
      <rect x="0.5" y="0.5" width="13" height="9" rx="2" fill={pattern ? `url(#${pattern.id})` : fill} stroke={stroke ?? 'none'} />
    </svg>
  );
}

/**
 * Net worth over 12 months, one bar per month-end. Every value comes from the backend
 * (services/net_worth_history.py, where net_worth = own − owe).
 *
 * Normal case: each bar stacks two values the API sends — `net_worth` (solid) and `owe`
 * (a light cap). Recharts piles them up, so the whole bar is as tall as `own` and the
 * solid part matches the net worth number on top. No sums here.
 *
 * If any month's net worth is below zero the stack would not read well, so the chart
 * shows plain "what you own" bars with net worth as a line instead.
 */
export function NetWorthChart({ points }: { points: NetWorthPoint[] }) {
  useThemeVersion();
  const solid = color('chart-1');
  const pale = color('chart-1', 0.3);
  const paleEdge = color('chart-1', 0.6);
  const stripesSolid = { id: STRIPES, fill: color('chart-1', 0.25), stripe: solid };
  const stripesPale = { id: STRIPES_PALE, fill: color('chart-1', 0.08), stripe: color('chart-1', 0.4) };
  const line = color('ink');
  const last = points.length - 1;
  const first = points[0];
  const end = points[last];
  const stacked = points.every((p) => p.net_worth >= 0);
  const summary = `Net worth went from ${fmtMoney(first.net_worth, { round: true })} at the end of ${first.label} to ${fmtMoney(end.net_worth, { round: true })} at the end of ${end.label}.`;

  /** The net worth number above each bar (stacked) or each line point (fallback). */
  const valueLabel = (props: unknown) => {
    const { x, y, width, value, index } = props as { x: number; y: number; width?: number; value: number; index: number };
    return (
      <text x={Number(x) + Number(width ?? 0) / 2} y={Number(y) - 8} textAnchor="middle" fontSize={12}
        fill={color(index === last ? 'ink' : 'ink-soft')} fontWeight={index === last ? 700 : 500}>
        {fmtMoney(value, { round: true })}
      </text>
    );
  };

  return (
    <div>
      <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-label text-ink-soft" aria-label="Chart legend">
        {stacked ? (
          <>
            <li className="flex items-center gap-1.5"><Swatch fill={solid} /> Net worth (number on top)</li>
            <li className="flex items-center gap-1.5"><Swatch fill={pale} stroke={paleEdge} /> Owed</li>
            <li>Whole bar = what you own</li>
          </>
        ) : (
          <>
            <li className="flex items-center gap-1.5"><Swatch fill={solid} /> What you own</li>
            <li className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-4" style={{ background: line }} aria-hidden /> Net worth (number on the line)</li>
          </>
        )}
        <li className="flex items-center gap-1.5"><Swatch fill={solid} pattern={{ ...stripesSolid, id: `${STRIPES}-legend` }} /> Estimated month</li>
      </ul>
      <div role="img" aria-label={summary} data-testid="net-worth-chart" data-mode={stacked ? 'stacked' : 'line'}>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={points} margin={{ top: 26, right: 8, bottom: 4, left: 4 }}>
            <defs>
              <Stripes {...stripesSolid} />
              <Stripes {...stripesPale} />
            </defs>
            <CartesianGrid vertical={false} stroke={color('border')} />
            <YAxis tickFormatter={fmtAxis} tickLine={false} axisLine={false} width={52} tick={{ fill: color('ink-muted'), fontSize: 12 }} />
            <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: color('border') }} interval={0} height={38}
              tick={(props: { x: number; y: number; payload: { index: number; value: string } }) => {
                const p = points[props.payload.index];
                return (
                  <g transform={`translate(${props.x},${props.y})`}>
                    <text dy={12} textAnchor="middle" fill={color('ink-muted')} fontSize={12}>{props.payload.value}</text>
                    {p?.estimated && <text dy={27} textAnchor="middle" fill={color('ink-soft')} fontSize={12} fontStyle="italic">estimated</text>}
                  </g>
                );
              }}
            />
            {!stacked && <ReferenceLine y={0} stroke={color('border-strong')} />}
            <Tooltip
              cursor={{ fill: color('neutral-tint') }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const p = payload[0].payload as NetWorthPoint;
                return (
                  <TooltipCard
                    title={
                      <>
                        End of {p.label}
                        {p.estimated && (
                          <span className="mt-0.5 block max-w-[240px] text-label font-normal text-ink-soft">
                            Estimated: {p.estimated_reasons.map((r) => REASON_WORD[r] ?? r).join('; ')}
                          </span>
                        )}
                      </>
                    }
                    rows={[
                      { label: 'You own', value: fmtMoney(p.own), swatch: stacked ? undefined : solid },
                      { label: 'You owe', value: p.owe ? `−${fmtMoney(p.owe)}` : fmtMoney(0), swatch: stacked ? pale : undefined },
                      { label: 'Net worth', value: fmtMoney(p.net_worth), swatch: stacked ? solid : line },
                    ]}
                  />
                );
              }}
            />
            {stacked ? (
              <>
                <Bar dataKey="net_worth" stackId="own" name="Net worth" maxBarSize={56} isAnimationActive={false}>
                  {points.map((p) => (
                    <Cell key={p.month} fill={p.estimated ? `url(#${STRIPES})` : solid} stroke={p.estimated ? solid : undefined} strokeWidth={p.estimated ? 1 : 0} />
                  ))}
                </Bar>
                <Bar dataKey="owe" stackId="own" name="Owed" maxBarSize={56} radius={[3, 3, 0, 0]} isAnimationActive={false}>
                  {points.map((p) => (
                    <Cell key={p.month} fill={p.estimated ? `url(#${STRIPES_PALE})` : pale} stroke={paleEdge} strokeWidth={1} />
                  ))}
                  <LabelList dataKey="net_worth" content={valueLabel} />
                </Bar>
              </>
            ) : (
              <>
                <Bar dataKey="own" name="What you own" maxBarSize={56} radius={[3, 3, 0, 0]} isAnimationActive={false}>
                  {points.map((p) => (
                    <Cell key={p.month} fill={p.estimated ? `url(#${STRIPES})` : solid} stroke={p.estimated ? solid : undefined} strokeWidth={p.estimated ? 1 : 0} />
                  ))}
                </Bar>
                <Line dataKey="net_worth" name="Net worth" stroke={line} strokeWidth={2} isAnimationActive={false}
                  dot={{ r: 3, fill: line, stroke: color('surface'), strokeWidth: 1.5 }} activeDot={{ r: 4 }}>
                  <LabelList dataKey="net_worth" content={valueLabel} />
                </Line>
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
