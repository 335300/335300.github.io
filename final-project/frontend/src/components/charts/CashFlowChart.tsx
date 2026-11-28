import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fmtAxis, fmtMoney, fmtSigned } from '../../lib/format';
import { color, useThemeVersion } from '../../lib/theme';
import type { HistoryRow } from '../../lib/types';
import { TooltipCard } from './ChartTooltip';

/**
 * Cash in next to cash out, month by month. Cash out is stacked: living costs
 * below, investments on top — so it is visible how much of the money that left
 * went into building an asset.
 */
export function CashFlowChart({ rows }: { rows: HistoryRow[] }) {
  useThemeVersion();
  const cashIn = color('positive');
  const costs = color('ink-soft', 0.6);
  const invested = color('invest');
  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barGap={3}>
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
                  { label: 'Cash in', value: fmtMoney(p.income), swatch: cashIn },
                  { label: 'Costs', value: fmtMoney(p.expenses), swatch: costs },
                  { label: 'Invested', value: fmtMoney(p.invested), swatch: invested },
                  { label: 'Cash out', value: fmtMoney(p.cash_out) },
                  { label: 'Kept', value: fmtSigned(p.net) },
                ]}
              />
            );
          }}
        />
        <Legend iconSize={10} wrapperStyle={{ fontSize: 12, color: color('ink-soft') }} />
        <Bar name="Cash in" dataKey="income" fill={cashIn} maxBarSize={22} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        <Bar name="Cash out: costs" dataKey="expenses" stackId="out" fill={costs} maxBarSize={22} isAnimationActive={false} />
        <Bar name="Cash out: invested" dataKey="invested" stackId="out" fill={invested} maxBarSize={22} radius={[3, 3, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
