import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fmtAxis, fmtMoney } from '../../lib/format';
import { color, useThemeVersion } from '../../lib/theme';
import type { HistoryRow } from '../../lib/types';
import { TooltipCard } from './ChartTooltip';

/**
 * Fixed and variable costs per month, stacked, with the 3-month average of the
 * variable part as a dashed line — the line shows the direction when single
 * months jump around. Every value comes from the backend.
 */
export function CostsChart({ rows }: { rows: HistoryRow[] }) {
  useThemeVersion();
  const fixed = color('primary');
  const variable = color('secondary');
  const average = color('ink');
  return (
    <ResponsiveContainer width="100%" height={250}>
      <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={color('border')} vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: color('border') }} tick={{ fill: color('ink-muted'), fontSize: 12 }} />
        <YAxis tickFormatter={fmtAxis} tickLine={false} axisLine={false} width={56} tick={{ fill: color('ink-muted'), fontSize: 12 }} />
        <Tooltip
          cursor={{ fill: color('neutral-tint') }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as HistoryRow;
            return (
              <TooltipCard
                title={p.label}
                rows={[
                  { label: 'Fixed costs', value: fmtMoney(p.fixed), swatch: fixed },
                  { label: 'Variable costs', value: fmtMoney(p.variable), swatch: variable },
                  { label: 'All costs', value: fmtMoney(p.expenses) },
                  ...(p.variable_avg3 !== null ? [{ label: 'Variable, 3-month average', value: fmtMoney(p.variable_avg3), swatch: average, dashed: true }] : []),
                ]}
              />
            );
          }}
        />
        <Legend iconSize={10} wrapperStyle={{ fontSize: 12, color: color('ink-soft') }} />
        <Bar name="Fixed costs" dataKey="fixed" stackId="costs" fill={fixed} maxBarSize={38} isAnimationActive={false} />
        <Bar name="Variable costs" dataKey="variable" stackId="costs" fill={variable} maxBarSize={38} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        <Line name="Variable, 3-month average" type="monotone" dataKey="variable_avg3" stroke={average} strokeWidth={2} strokeDasharray="5 4"
          dot={false} connectNulls={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
