import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import { fmtMoney, fmtSigned } from '../../lib/format';
import { color, useThemeVersion } from '../../lib/theme';
import type { JointHousehold } from '../../lib/types';
import { TooltipCard } from './ChartTooltip';

type Row = JointHousehold['months'][number];

const label = (v: unknown) => (typeof v === 'number' && v > 0 ? fmtMoney(v, { round: true }) : '');

/**
 * The Joint Overview's simple history: what we put in next to what we spent,
 * one pair of bars per month, each with its amount written on top — nothing
 * to read off an axis. Every value comes from the backend (services/joint.py).
 */
export function JointMonthsChart({ rows }: { rows: Row[] }) {
  useThemeVersion();
  const putIn = color('positive');
  const spent = color('primary');
  return (
    <div>
      <ul className="mb-1 flex gap-4 text-label text-ink-soft" aria-label="Chart legend">
        <li className="flex items-center gap-1.5"><span className="h-2.5 w-3.5 rounded-sm" style={{ background: putIn }} /> We put in</li>
        <li className="flex items-center gap-1.5"><span className="h-2.5 w-3.5 rounded-sm" style={{ background: spent }} /> We spent</li>
      </ul>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={{ top: 22, right: 8, bottom: 0, left: 8 }} barGap={4}>
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: color('border') }} tick={{ fill: color('ink-soft'), fontSize: 14 }} />
          <Tooltip
            cursor={{ fill: color('neutral-tint') }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const r = payload[0].payload as Row;
              return (
                <TooltipCard
                  title={r.label}
                  rows={[
                    { label: 'We put in', value: fmtMoney(r.put_in), swatch: putIn },
                    { label: 'We spent', value: fmtMoney(r.spent), swatch: spent },
                    { label: 'Left over', value: fmtSigned(r.kept) },
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="put_in" name="We put in" fill={putIn} maxBarSize={30} radius={[4, 4, 0, 0]} isAnimationActive={false}>
            <LabelList dataKey="put_in" position="top" formatter={label} style={{ fill: color('ink-soft'), fontSize: 14 }} />
          </Bar>
          <Bar dataKey="spent" name="We spent" fill={spent} maxBarSize={30} radius={[4, 4, 0, 0]} isAnimationActive={false}>
            <LabelList dataKey="spent" position="top" formatter={label} style={{ fill: color('ink-soft'), fontSize: 14 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
