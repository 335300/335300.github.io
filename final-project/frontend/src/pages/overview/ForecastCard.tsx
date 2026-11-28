import { useForecast } from '../../api/queries';
import { ForecastChart, type ForecastPoint } from '../../components/charts/ForecastChart';
import { Card, EmptyState } from '../../components/ui/Card';
import { ErrorNote } from '../../components/ui/Feedback';
import { Skeleton } from '../../components/ui/States';
import { fmtMoney } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { ForecastRangeMonth, RollingForecast } from '../../lib/types';

/** How many planned months the Overview card shows (the backend's `first_6` summary covers the same). */
const AHEAD = 6;

/**
 * The rolling forecast's recorded months and its first six planned months as
 * chart points. Reshaping only: balances and bands come from /api/forecast.
 */
export function forecastPoints(f: RollingForecast, ahead = AHEAD): ForecastPoint[] {
  const key = f.ranges?.line_key ?? f.lines[0]?.key;
  if (!key) return [];
  const bands = new Map<string, ForecastRangeMonth>((f.ranges?.months ?? []).map((m) => [m.key, m]));
  const recorded = f.rows.filter((r) => r.actual);
  const planned = f.rows.filter((r) => !r.actual).slice(0, ahead);
  return [...recorded, ...planned].map((r) => {
    const balance = r.values[key]?.balance ?? null;
    const band = bands.get(r.key);
    return {
      label: r.label,
      title: `${r.month_name} · ${r.actual ? 'recorded' : 'planned'}`,
      actual: r.actual ? balance : null,
      likely: r.actual ? null : balance,
      band50: band ? [band.low50, band.high50] : null,
      band80: band ? [band.low80, band.high80] : null,
      negative: balance !== null && balance < 0,
    };
  });
}

/** Forecast · next 6 months (Personal Overview). */
export function ForecastCard() {
  const { data, error, isLoading } = useForecast();
  const setTab = useUi((s) => s.setTab);
  const r = data?.ranges?.first_6;
  const points = data ? forecastPoints(data) : [];

  return (
    <Card title="Forecast · next 6 months" link={{ label: 'Open forecast', onClick: () => setTab('forecast') }} testId="overview-forecast">
      {isLoading ? (
        <Skeleton lines={5} />
      ) : error ? (
        <ErrorNote error={error} />
      ) : points.length === 0 ? (
        <EmptyState title="No forecast yet">Record a month of transactions to see where your balance is heading.</EmptyState>
      ) : (
        <>
          {r && data?.ranges && (
            <div className="num mb-2 flex flex-col gap-0.5">
              <span className="text-body font-semibold text-ink">
                In 8 of 10 likely futures you stay above {fmtMoney(r.floor_80, { round: true })} through {r.horizon_end_month}.
              </span>
              <span className="text-[13px] leading-[18px] text-ink-soft">
                Most likely balance in {r.horizon_end_month}: about {fmtMoney(r.likely_end_about, { round: true })}. Based on{' '}
                {data.ranges.history_months} months of history and your planned bills.
              </span>
            </div>
          )}
          {/* The sentence above already names the most likely balance, so the narrow card leaves it off the right edge. */}
          <ForecastChart points={points} height={240} likelyWord={null} />
        </>
      )}
    </Card>
  );
}
