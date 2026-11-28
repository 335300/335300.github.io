import { useBudgets, useJointBill, useJointHousehold, useProjection, useYears } from '../../api/queries';
import { ForecastChart, type ForecastPoint } from '../../components/charts/ForecastChart';
import { Card, EmptyState, Hint } from '../../components/ui/Card';
import { CategoryDot } from '../../components/ui/CategoryDot';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { KpiTile } from '../../components/ui/KpiTile';
import { StatusBadge, StatusIcon } from '../../components/ui/StatusBadge';
import { fmtMoney } from '../../lib/format';
import type { JointBill } from '../../lib/types';
import { BudgetGrid } from './BudgetGrid';
import { GoalsPanel } from './GoalsPanel';
import { StartingPoint } from './StartingPoint';

/**
 * The Joint profile's Forecast, simple and in plain English for Isa: where our
 * shared pot is heading, what we put in and spend each month, what we pay,
 * what we buy together, and the plan itself. Every figure comes from the
 * backend (services/joint.py → bill_forecast, forecast_ranges.for_joint).
 */
export function JointForecast({ year, today }: { year: number; today: string }) {
  const bill = useJointBill();
  const projection = useProjection(year);
  const years = useYears();
  const yearInfo = years.data?.years.find((y) => y.year === year);
  const nowMonth = years.data && years.data.current_year === year ? years.data.current_month : 11;
  const household = useJointHousehold(year, nowMonth);
  if (bill.isLoading || projection.isLoading) return <Loading />;
  if (bill.error || !bill.data) return <ErrorNote error={bill.error} />;
  const f = bill.data;
  const lastActual = projection.data?.summary.last_actual_month ?? null;
  const goalShares = new Map((household.data?.goals.rows ?? []).map((g) => [g.id, g]));

  const shareLine = (id: number) => {
    const g = goalShares.get(id);
    if (!g || g.monthly === null || g.monthly <= 0) return null;
    return (
      <span className="num">
        {fmtMoney(g.monthly)} a month gets us there on time
        {g.a !== null && g.b !== null ? ` — ${fmtMoney(g.a)} from ${f.names.a}, ${fmtMoney(g.b)} from ${f.names.b}.` : '.'}
      </span>
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <span className="text-[15px] text-ink-soft">
          What’s coming{f.start_name && f.end_name ? ` · ${f.start_name} to ${f.end_name}` : ''}
        </span>
        <h1 className="text-[32px] font-semibold leading-10 text-ink" data-testid="joint-headline">
          {!f.rows.length
            ? 'Our plan appears once a year is set up.'
            : f.goes_negative
              ? `Careful: our shared account would drop below zero in ${f.lowest_name}.`
              : `Our plan works: about ${fmtMoney(f.end_pot, { round: true })} in our shared account by ${f.end_name}.`}
        </h1>
        {f.ranges && (
          <p className="num text-base text-ink-soft">
            In 8 of 10 likely futures our shared account stays above {fmtMoney(f.ranges.floor_80, { round: true })} until {f.ranges.horizon_end_month}.
          </p>
        )}
      </div>

      {f.average && <Tiles data={f} />}

      {f.goes_negative && (
        <div className="flex items-center gap-3 rounded-lg border border-line bg-negative-tint px-4 py-3 text-[15px]">
          <StatusBadge kind="negative">Below zero</StatusBadge>
          <span>
            Our shared account would drop below zero in {f.lowest_name}. A goal costs more than we will have saved by then — move its date,
            or save a bit more each month.
          </span>
        </div>
      )}

      <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] items-start gap-5">
        <div className="flex min-w-0 flex-col gap-5">
          <Card title="Money in our shared account" testId="joint-pot-chart">
            {f.rows.length ? <PotChart data={f} /> : <Hint>Nothing planned yet.</Hint>}
            <p className="mt-2 text-sm text-ink-soft">
              Dashed line: where our shared account is most likely heading.{f.ranges ? ' Shaded area: the range we’d expect.' : ''}
            </p>
          </Card>
          <Card title="Month by month" bodyClassName="!px-0" testId="joint-month-by-month">
            {f.rows.length ? <BillTable data={f} /> : <div className="px-5"><Hint>Nothing planned yet.</Hint></div>}
            {f.rows.length > 0 && f.rows.every((r) => r.total === 0) && (
              <div className="px-5 pt-2"><Hint>No costs planned yet. Fill in our plan below (rent, groceries, …).</Hint></div>
            )}
          </Card>
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <WhatWePay data={f} year={year} />
          <GoalsPanel year={year} today={today} shared title="We buy" shareLine={shareLine} />
        </div>
      </div>

      <Card title={`Our plan ${year}`} bodyClassName="!px-0"
        subtitle="What we plan to spend together each month. The “From …” rows follow it by themselves: each of us pays in our part.">
        <BudgetGrid year={year} lastActual={lastActual} simple />
      </Card>

      {yearInfo && (
        <p className="text-sm text-ink-soft">
          <StartingPoint key={`${yearInfo.opening_balance}-${yearInfo.start_month}`} year={yearInfo} joint />.
        </p>
      )}
    </div>
  );
}

function Tiles({ data }: { data: JointBill }) {
  const avg = data.average!;
  return (
    <div className="grid grid-cols-4 gap-4" data-testid="joint-bill-tiles">
      <KpiTile label="Together each month" value={`≈ ${fmtMoney(avg.total, { round: true })}`}
        meta={`${data.names.a} ≈ ${fmtMoney(avg.a, { round: true })} (${data.split.share_a_pct}%) · ${data.names.b} ≈ ${fmtMoney(avg.b, { round: true })} (${data.split.share_b_pct}%)`} />
      <KpiTile label="Our costs" value={`≈ ${fmtMoney(avg.costs, { round: true })}`} meta="What we spend in an average month." />
      <KpiTile label="For our goals" value={`≈ ${fmtMoney(avg.goals, { round: true })}`}
        meta={avg.goals > 0 ? 'Set aside each month for what we buy together.' : 'Nothing set aside for goals yet.'} />
      <KpiTile label={`In our pot, end of ${data.end_name}`} value={fmtMoney(data.end_pot)}
        tone={data.end_pot < 0 ? 'negative' : 'neutral'} alert={data.goes_negative}
        meta={data.goes_negative ? `Below zero: lowest ${fmtMoney(data.lowest_pot)} in ${data.lowest_name}` : 'If we both pay in our part.'} />
    </div>
  );
}

/** The pot month by month: today's balance, then the most likely path and the ranges. Reshaping only. */
function PotChart({ data }: { data: JointBill }) {
  const byKey = new Map((data.ranges?.months ?? []).map((m) => [m.key, m]));
  const points: ForecastPoint[] = [
    { label: 'Now', title: 'Now · in our shared account', actual: data.start_balance },
    ...data.rows.map((r) => {
      const m = byKey.get(r.key);
      return {
        label: r.label,
        title: r.month_name,
        likely: r.pot,
        band50: m ? [m.low50, m.high50] as [number, number] : null,
        band80: m ? [m.low80, m.high80] as [number, number] : null,
        negative: r.pot < 0,
        details: [
          { label: 'We put in', value: fmtMoney(r.total) },
          { label: 'We spend', value: fmtMoney(r.costs) },
          ...(r.goals ? [{ label: 'For our goals', value: fmtMoney(r.goals) }] : []),
          ...r.goals_bought.map((g) => ({ label: `We buy: ${g.name}`, value: fmtMoney(g.amount) })),
        ],
      };
    }),
  ];
  return <ForecastChart points={points} todayLabel="Now" height={250} />;
}

function BillTable({ data }: { data: JointBill }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table [&_td:first-child]:pl-6 [&_td:last-child]:pr-6 [&_th:first-child]:pl-6 [&_th:last-child]:pr-6">
        <thead>
          <tr>
            <th>Month</th>
            <th className="text-right">We put in</th>
            <th className="text-right">We spend</th>
            <th className="text-right">For our goals</th>
            <th className="text-right">In our pot after</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.key}>
              <td className="cell-wrap py-2">
                <span className="font-medium">{r.month_name}</span>
                {r.goals_bought.length > 0 && (
                  <span className="chip ml-2">We buy: {r.goals_bought.map((g) => g.name).join(', ')}</span>
                )}
              </td>
              <td className="cell-num py-2">
                <span className="block text-positive">{fmtMoney(r.total)}</span>
                <span className="block text-ink-soft">{data.names.a} {fmtMoney(r.a)} · {data.names.b} {fmtMoney(r.b)}</span>
              </td>
              <td className="cell-num">{fmtMoney(r.costs)}</td>
              <td className="cell-num text-secondary">{r.goals ? fmtMoney(r.goals) : '—'}</td>
              <td className="cell-num font-semibold">
                {r.pot < 0
                  ? <span className="inline-flex items-center gap-1 text-negative"><StatusIcon kind="negative" /> Below zero: {fmtMoney(r.pot)}</span>
                  : fmtMoney(r.pot)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** What our plan says we pay in the first coming month, category by category (from the budget plan). */
function WhatWePay({ data, year }: { data: JointBill; year: number }) {
  const first = data.rows.find((r) => r.year === year) ?? data.rows[0];
  const budgets = useBudgets(first?.year ?? year);
  const month = first?.month ?? 0;
  const rows = (budgets.data?.expense.rows ?? []).filter((r) => r.values[month] > 0);
  return (
    <Card title="What we pay each month" testId="joint-what-we-pay"
      subtitle={first ? `What our plan says for ${first.month_name}.` : undefined}>
      {!first ? <Hint>Nothing planned yet.</Hint> : budgets.isLoading ? <Loading /> : budgets.error ? (
        <Hint>Our plan for {first.month_name} appears once that year is set up.</Hint>
      ) : rows.length ? (
        <ul className="divide-y divide-line">
          {rows.map((r) => (
            <li key={r.cat} className="flex h-11 items-center justify-between gap-3 text-[15px]">
              <span className="flex min-w-0 items-center gap-2"><CategoryDot cat={r.cat} kind={r.kind} /><span className="truncate">{r.cat}</span></span>
              <span className="num font-medium">{fmtMoney(r.values[month])}</span>
            </li>
          ))}
          {budgets.data && (
            <li className="flex h-12 items-center justify-between gap-3 text-[15px] font-semibold">
              <span>Together</span>
              <span className="num">{fmtMoney(budgets.data.expense.monthly_totals[month])}</span>
            </li>
          )}
        </ul>
      ) : (
        <EmptyState title="Nothing planned yet">Fill in our plan below (rent, groceries, …).</EmptyState>
      )}
    </Card>
  );
}
