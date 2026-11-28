import { useJointBill } from '../../api/queries';
import { ForecastChart, type ForecastPoint } from '../../components/charts/ForecastChart';
import { Card, EmptyState } from '../../components/ui/Card';
import { ErrorNote } from '../../components/ui/Feedback';
import { Skeleton } from '../../components/ui/States';
import { fmtMoney } from '../../lib/format';
import type { ForecastRangeMonth } from '../../lib/types';

const AHEAD = 6;

/**
 * "Looking ahead" (Joint Overview, for Isa): our shared account today and the
 * next six months of the Joint plan, with the likely ranges. Every balance and
 * band comes from /api/joint/bill; the chart only draws them.
 */
export function JointLookingAhead({ className = '' }: { className?: string }) {
  const { data, error, isLoading } = useJointBill();
  const ranges = data?.ranges ?? null;
  const r = ranges?.first_6;
  const rows = (data?.rows ?? []).slice(0, AHEAD);
  const bands = new Map<string, ForecastRangeMonth>((ranges?.months ?? []).map((m) => [m.key, m]));
  const points: ForecastPoint[] = data && rows.length
    ? [
        { label: 'Today', title: 'Today', actual: data.start_balance },
        ...rows.map((row) => {
          const band = bands.get(row.key);
          return {
            label: row.label,
            title: row.month_name,
            likely: row.pot,
            band50: band ? [band.low50, band.high50] as [number, number] : null,
            band80: band ? [band.low80, band.high80] as [number, number] : null,
            negative: row.pot < 0,
          };
        }),
      ]
    : [];
  const last = rows[rows.length - 1];

  return (
    <Card title="Looking ahead" className={className} testId="joint-looking-ahead">
      {isLoading ? (
        <Skeleton lines={5} />
      ) : error ? (
        <ErrorNote error={error} />
      ) : points.length === 0 ? (
        <EmptyState title="Nothing planned yet">Plan our costs in the Forecast tab to see what lies ahead.</EmptyState>
      ) : (
        <>
          <p className="num mb-2 text-body text-ink">
            {r
              ? <>In 8 of 10 likely futures our shared account stays above <b>{fmtMoney(r.floor_80, { round: true })}</b> until {r.horizon_end_month}.</>
              : last && <>If everything goes to plan, our shared account will have about <b>{fmtMoney(last.pot, { round: true })}</b> in {last.month_name}.</>}
          </p>
          <ForecastChart points={points} todayLabel="Today" height={240} />
          <p className="mt-2 text-body text-ink-soft">
            The dot is today. Dashed line: the most likely path.
            {ranges && ' Shaded area: the range we’d expect — wider further out because the future is less certain.'}
          </p>
        </>
      )}
    </Card>
  );
}
