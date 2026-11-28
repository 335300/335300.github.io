import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import { Flag } from 'lucide-react';
import { fmtMoney } from '../../lib/format';
import { color, useThemeVersion } from '../../lib/theme';
import type { JointBill } from '../../lib/types';
import { TooltipCard } from './ChartTooltip';

type Row = JointBill['rows'][number];

const label = (v: unknown) => (typeof v === 'number' && v > 0 ? fmtMoney(v, { round: true }) : '');

/**
 * What we pay together each month: one bar per month, split into each
 * person's part (their colour, named in the legend), the month's total written
 * on top. A flag under the month marks a goal we buy then. Every value comes
 * from the backend (services/joint.py → bill_forecast).
 */
export function JointBillChart({ data }: { data: JointBill }) {
  useThemeVersion();
  const a = color('primary');
  const b = color('secondary');
  const goalMonths = new Set(data.rows.filter((r) => r.goals_bought.length).map((r) => r.label));
  return (
    <div>
      <ul className="mb-1 flex flex-wrap gap-4 text-label text-ink-soft" aria-label="Chart legend">
        <li className="flex items-center gap-1.5"><span className="h-2.5 w-3.5 rounded-sm" style={{ background: a }} /> {data.names.a}’s part</li>
        <li className="flex items-center gap-1.5"><span className="h-2.5 w-3.5 rounded-sm" style={{ background: b }} /> {data.names.b}’s part</li>
        {goalMonths.size > 0 && (
          <li className="flex items-center gap-1.5"><Flag size={12} style={{ color: color('positive') }} /> We buy a goal that month</li>
        )}
      </ul>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data.rows} margin={{ top: 22, right: 8, bottom: 0, left: 8 }}>
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: color('border') }} interval={0}
            tick={(props) => <MonthTick {...props} flagged={goalMonths} />} height={38} />
          <Tooltip
            cursor={{ fill: color('neutral-tint') }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const r = payload[0].payload as Row;
              return (
                <TooltipCard
                  title={r.month_name}
                  rows={[
                    { label: 'Our costs', value: fmtMoney(r.costs) },
                    ...(r.goals ? [{ label: 'Saved for our goals', value: fmtMoney(r.goals) }] : []),
                    { label: `${data.names.a} pays`, value: fmtMoney(r.a), swatch: a },
                    { label: `${data.names.b} pays`, value: fmtMoney(r.b), swatch: b },
                    ...r.goals_bought.map((g) => ({ label: `We buy: ${g.name}`, value: `−${fmtMoney(g.amount)}`, swatch: color('positive') })),
                    { label: 'In our pot after', value: fmtMoney(r.pot) },
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="a" stackId="pay" name={data.names.a} fill={a} maxBarSize={34} isAnimationActive={false} />
          <Bar dataKey="b" stackId="pay" name={data.names.b} fill={b} maxBarSize={34} radius={[4, 4, 0, 0]} isAnimationActive={false}>
            <LabelList dataKey="total" position="top" formatter={label} style={{ fill: color('ink-soft'), fontSize: 14 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** The month name, with a small flag under it when a goal is bought that month. */
function MonthTick(props: { x?: number | string; y?: number | string; payload?: { value: string }; flagged: Set<string> }) {
  const x = Number(props.x ?? 0);
  const y = Number(props.y ?? 0);
  const value = props.payload?.value ?? '';
  return (
    <g transform={`translate(${x},${y})`}>
      <text dy={12} textAnchor="middle" fill={color('ink-soft')} fontSize={14}>{value}</text>
      {props.flagged.has(value) && (
        <path transform="translate(-4,18)" d="M0 0 V12 M0 1 H8 L6 4 L8 7 H0" fill={color('positive', 0.25)} stroke={color('positive')} strokeWidth={1.25}
          aria-label={`A goal is bought in ${value}`} />
      )}
    </g>
  );
}
