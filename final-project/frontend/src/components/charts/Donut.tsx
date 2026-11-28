import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { fmtMoney, fmtPct } from '../../lib/format';
import { color, useThemeVersion } from '../../lib/theme';
import { TooltipCard } from './ChartTooltip';

interface Slice {
  name: string;
  value: number;
  share: number;
  token: 'primary' | 'secondary';
}

/** Fixed vs variable costs. Values and shares come from the backend. */
export function Donut({ fixed, variable, total }: {
  fixed: { total: number; share: number };
  variable: { total: number; share: number };
  total: number;
}) {
  useThemeVersion();
  const data: Slice[] = [
    { name: 'Fixed costs', value: fixed.total, share: fixed.share, token: 'primary' },
    { name: 'Variable costs', value: variable.total, share: variable.share, token: 'secondary' },
  ];
  return (
    <div className="relative h-44 w-44 shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="68%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
            stroke={color('surface')}
            strokeWidth={2}
            isAnimationActive={false}
          >
            {data.map((d) => (
              <Cell key={d.name} fill={color(d.token)} />
            ))}
          </Pie>
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as Slice;
              return <TooltipCard title={d.name} rows={[{ label: 'Amount', value: fmtMoney(d.value) }, { label: 'Share', value: fmtPct(d.share) }]} />;
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-label text-ink-soft">Spent</span>
        <span className="num text-base font-semibold">{fmtMoney(total, { round: true })}</span>
      </div>
    </div>
  );
}
