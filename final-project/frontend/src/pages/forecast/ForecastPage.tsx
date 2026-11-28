import { useState } from 'react';
import { useStoredFlag } from '../../lib/useCollapsed';
import { useForecast, useGoals, useProfiles, useProjection, useYears } from '../../api/queries';
import { RollingForecastChart, type ForecastBand } from '../../components/charts/RollingForecastChart';
import { Card, Hint } from '../../components/ui/Card';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { KpiTile } from '../../components/ui/KpiTile';
import { StatusBadge, type StatusKind } from '../../components/ui/StatusBadge';
import { fmtMoney, fmtSigned } from '../../lib/format';
import type { GoalsResponse, RollingForecast, RollingLine, RollingRow } from '../../lib/types';
import { BudgetGrid, BudgetModeToggle, useBudgetMode } from './BudgetGrid';
import { GoalForm } from './GoalForm';
import { GoalsPanel } from './GoalsPanel';
import { IncomeCalendarCard } from './IncomeCalendarCard';
import { InvestmentsPanel } from './InvestmentsPanel';
import { JointForecast } from './JointForecast';
import { RollingTable } from './RollingTable';
import { StartingPoint } from './StartingPoint';

export function ForecastPage({ year }: { year: number }) {
  const isJoint = useProfiles().data?.active === 'joint';
  const today = useYears().data?.today ?? new Date().toISOString().slice(0, 10);
  return isJoint ? <JointForecast year={year} today={today} /> : <PersonalForecast year={year} />;
}

const GRID_COLS: Record<number, string> = { 1: 'grid-cols-1', 2: 'grid-cols-2', 3: 'grid-cols-3', 4: 'grid-cols-4' };

/** The line with the lowest point (picking one line — no arithmetic). */
const lowestLine = (lines: RollingLine[]) => lines.reduce((a, b) => (b.lowest_balance < a.lowest_balance ? b : a));

function PersonalForecast({ year }: { year: number }) {
  const [withGoals, toggleGoals] = useStoredFlag('pc-forecast-with-goals', true);
  const forecast = useForecast(withGoals);
  const projection = useProjection(year);
  const goals = useGoals(year);
  const years = useYears();
  const [mode, setMode] = useBudgetMode();
  const [creatingGoal, setCreatingGoal] = useState(false);
  const [incomeSettings, setIncomeSettings] = useState(false);
  const yearInfo = years.data?.years.find((y) => y.year === year);
  const today = years.data?.today ?? new Date().toISOString().slice(0, 10);

  if (forecast.isLoading || projection.isLoading) return <Loading />;
  if (forecast.error || !forecast.data) return <ErrorNote error={forecast.error} />;
  const f = forecast.data;
  const lastActual = projection.data?.summary.last_actual_month ?? null;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-end justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-0.5">
          <h1 className="text-page-title text-ink">Forecast</h1>
          <p className="text-[13px] text-ink-soft" data-testid="forecast-subtitle">
            Next 12 months
            {f.ranges ? ` · from ${f.ranges.history_months} months of history, your budgets and planned bills` : ' · from your budgets and planned bills'}
            {yearInfo && <> · <StartingPoint key={`${yearInfo.opening_balance}-${yearInfo.start_month}`} year={yearInfo} /></>}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button type="button" className="btn-secondary" onClick={() => setIncomeSettings(true)}>Income settings</button>
          <button type="button" className="btn-primary" onClick={() => setCreatingGoal(true)}>Add goal</button>
        </div>
      </div>

      {f.lines.length > 0 && <Tiles f={f} goals={goals.data} />}

      <BalanceCard f={f} goals={goals.data} withGoals={withGoals} toggleGoals={toggleGoals} />

      <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)] items-start gap-4">
        <Card title="Month by month" meta="most likely figures · balance at month end" bodyClassName="!px-0" testId="month-by-month">
          {f.rows.length > 0 ? <RollingTable data={f} /> : <div className="px-5"><Hint>Nothing to forecast yet.</Hint></div>}
        </Card>
        <div className="flex min-w-0 flex-col gap-4">
          <GoalsPanel year={year} today={today} />
          <InvestmentsPanel year={year} today={today} />
        </div>
      </div>

      <IncomeCalendarCard year={year} settingsOpen={incomeSettings} onSettingsClose={() => setIncomeSettings(false)} />

      <Card title="Plan by month" meta={`${year} · grey italic = filled in for you · ↺ = typed by hand`}
        action={<BudgetModeToggle mode={mode} onChange={setMode} />} bodyClassName="!px-0" testId="plan-by-month">
        <BudgetGrid year={year} lastActual={lastActual} mode={mode} />
      </Card>

      {creatingGoal && <GoalForm open today={today} onClose={() => setCreatingGoal(false)} />}
    </div>
  );
}

/** Headline tiles: balance in 12 months (one per scenario), lowest point, free to use, expected per month. */
function Tiles({ f, goals }: { f: RollingForecast; goals?: GoalsResponse }) {
  const many = f.lines.length > 1;
  const low = lowestLine(f.lines);
  const anyNegative = f.lines.some((l) => l.goes_negative);
  const single = f.lines.length === 1 ? f.lines[0] : null;
  const showFree = !!single && !!f.include_goals && single.lowest_free !== null && single.lowest_free !== undefined;
  const showExpected = f.lines.length < 3;
  const count = f.lines.length + 1 + (showFree ? 1 : 0) + (showExpected ? 1 : 0);

  return (
    <div className={`grid gap-4 ${GRID_COLS[Math.min(count, 4)]}`} data-testid="forecast-tiles">
      {f.lines.map((l) => (
        <KpiTile key={l.key} variant="hero"
          label={many ? `In 12 months · ${l.name}` : `Balance end of ${f.end_name}`}
          value={fmtMoney(l.end_balance)}
          tone={l.end_balance < 0 ? 'negative' : 'neutral'}
          alert={l.end_balance < 0}
          help="The balance at the end of the 12 months, if you earn and spend as planned."
          meta={`${fmtSigned(l.kept, { round: true })} kept · ${fmtSigned(l.average_kept, { round: true })} a month`} />
      ))}
      <KpiTile variant="hero" label="Lowest point" value={fmtMoney(low.lowest_balance)}
        tone={anyNegative ? 'negative' : 'neutral'} alert={anyNegative}
        help="The lowest month-end balance in the next 12 months (most likely figures)."
        meta={`${anyNegative ? 'Below zero · ' : ''}${low.lowest_label ?? ''} · most likely month-end balance${many ? ` · ${low.name}` : ''}${f.goals_spent ? ' · after goal purchases' : ''}`} />
      {showFree && single && (
        <KpiTile variant="hero" label="Free to use · lowest" value={fmtMoney(single.lowest_free!)}
          tone={single.lowest_free! < 0 ? 'negative' : 'neutral'} alert={single.lowest_free! < 0}
          help="The balance minus the money set aside for goals, at its lowest month."
          meta={`${single.lowest_free! < 0 ? 'Goals need more than the account holds · ' : ''}${single.lowest_free_label ?? ''} · after money set aside for goals`} />
      )}
      {showExpected && (
        <KpiTile variant="hero" label="Expected per month" value={fmtSigned(goals?.summary.expected_monthly_savings ?? 0, { round: true })}
          help="What a month keeps on average over the next 12 months (cash in − cash out). Your goals are checked against it."
          meta="Kept on average, before goal purchases" />
      )}
    </div>
  );
}

/** The status line under the chart. Only reads statuses the backend sent. */
function statusOf(f: RollingForecast, goals?: GoalsResponse): { kind: StatusKind; badge: string; title: string; text: string } | null {
  if (!f.lines.length) return null;
  const low = lowestLine(f.lines);
  if (!low.lowest_label) return null;
  if (f.lines.some((l) => l.goes_negative)) {
    return { kind: 'negative', badge: 'Below zero', title: `Your balance drops below zero in ${low.lowest_label}.`,
      text: 'Look at the plan by month for those months, or plan income for them.' };
  }
  const tight = goals?.goals.find((g) => g.forecast && !g.forecast.affordable && g.status !== 'completed' && g.status !== 'abandoned');
  if (tight?.forecast) {
    return { kind: 'warning', badge: 'Heads-up', title: `${tight.name}: not covered in ${tight.forecast.month_name}.`,
      text: `The balance would be ${fmtMoney(tight.forecast.balance)} then${tight.forecast.line ? ` (${tight.forecast.line})` : ''}.` };
  }
  const single = f.lines.length === 1 ? f.lines[0] : null;
  if (single && single.lowest_free !== null && single.lowest_free !== undefined && single.lowest_free < 0) {
    return { kind: 'warning', badge: 'Heads-up', title: `Goals need more than the account holds in ${single.lowest_free_label ?? low.lowest_label}.`,
      text: `Free to use drops to ${fmtMoney(single.lowest_free)}.` };
  }
  const s = goals?.summary;
  if (s && s.open_goals > 1 && !s.combined_covered) {
    return { kind: 'warning', badge: 'Heads-up', title: 'Your open goals need more than you keep.',
      text: `Together they need ${fmtMoney(s.total_required_pace)} a month; the forecast expects ${fmtMoney(s.expected_monthly_savings)} — ${fmtMoney(s.combined_shortfall)} short.` };
  }
  return { kind: 'positive', badge: 'On track', title: `Tightest month: ${low.lowest_label}.`,
    text: `The balance is lowest at ${fmtMoney(low.lowest_balance)} and stays above zero. Nothing to do.` };
}

function BalanceCard({ f, goals, withGoals, toggleGoals }: {
  f: RollingForecast;
  goals?: GoalsResponse;
  withGoals: boolean;
  toggleGoals: () => void;
}) {
  const r = f.ranges;
  const flat = f.lines.length > 0 && f.lines.every((l) => l.kept === 0);
  const firstKey = f.lines[0]?.key;
  // Bands for the first line, matched by month key. The last recorded month starts the band at its own balance (no maths).
  const byKey = new Map((r?.months ?? []).map((m) => [m.key, m]));
  const lastRecorded = f.rows.reduce<RollingRow | undefined>((last, row) => (row.actual ? row : last), undefined);
  const bands = r ? (row: RollingRow): ForecastBand | null => {
    const m = byKey.get(row.key);
    if (m) return { band50: [m.low50, m.high50], band80: [m.low80, m.high80] };
    if (row === lastRecorded && firstKey) {
      const b = row.values[firstKey].balance;
      return { band50: [b, b], band80: [b, b] };
    }
    return null;
  } : undefined;
  const purchases = f.include_goals
    ? f.rows.flatMap((row) => (row.goals ?? []).map((g) => `${g.name} in ${row.month_name} (${fmtMoney(g.amount)})`))
    : [];
  const status = statusOf(f, goals);

  return (
    <Card title="Projected balance — next 12 months" testId="projected-balance"
      action={
        <label className="flex cursor-pointer items-center gap-2 whitespace-nowrap text-[13px] font-medium text-ink">
          <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--c-primary))]" checked={withGoals} onChange={toggleGoals} aria-label="Include goal purchases" />
          Include goal purchases
        </label>
      }>
      <div className="flex flex-col gap-3">
        {(r || purchases.length > 0 || !f.include_goals) && (
          <div className="flex flex-col gap-0.5" data-testid="forecast-ranges">
            {r && (
              <p className="num text-[15px] font-semibold leading-[21px] text-ink">
                In 8 of 10 likely futures you stay above {fmtMoney(r.floor_80, { round: true })} through {r.horizon_end_month}.
              </p>
            )}
            <p className="num text-[13px] text-ink-soft">
              {r && <>Most likely balance in {r.horizon_end_month}: about {fmtMoney(r.likely_end_about, { round: true })}. Based on {r.history_months} months of history. </>}
              {purchases.length > 0 && <>Includes buying {purchases.join('; ')} from your goal money.</>}
              {!f.include_goals && 'Without goal purchases.'}
            </p>
          </div>
        )}
        {f.rows.length ? <RollingForecastChart rows={f.rows} lines={f.lines} bands={bands} /> : <Hint>Nothing to forecast yet.</Hint>}
        {f.borrowed_budget_years && f.borrowed_budget_years.length > 0 && (
          <Hint>Next year is not set up yet, so its months use the {f.borrowed_budget_years.join(', ')} budget for the same month.</Hint>
        )}
        {flat && <Hint>No budget set for the coming months yet, so the planned part is flat. Fill in the plan by month below.</Hint>}
        {status && (
          <div className="flex items-center gap-4 rounded-lg border border-line bg-bg px-4 py-3" data-testid="forecast-status">
            <StatusBadge kind={status.kind}>{status.badge}</StatusBadge>
            <p className="num flex-1 text-body"><b className="font-semibold">{status.title}</b> <span className="text-ink-soft">{status.text}</span></p>
          </div>
        )}
      </div>
    </Card>
  );
}
