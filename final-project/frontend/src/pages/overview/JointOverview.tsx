import { ArrowUpRight, CalendarClock, Check, PiggyBank, Target, Users } from 'lucide-react';
import { useAttention, useBillsCalendar, useDashboard, useJointHousehold } from '../../api/queries';
import { JointMonthsChart } from '../../components/charts/JointMonthsChart';
import { Card, EmptyState, Hint } from '../../components/ui/Card';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { KpiTile } from '../../components/ui/KpiTile';
import { ProgressBar, type BarTone } from '../../components/ui/ProgressBar';
import { budgetBarTone, GoalBadge, StatusBadge, StatusText } from '../../components/ui/StatusBadge';
import { fmtDate, fmtMoney } from '../../lib/format';
import { useUi } from '../../lib/store';
import type { BudgetStatus, Dashboard, JointHousehold, Person } from '../../lib/types';
import { JointLookingAhead } from './JointLookingAhead';
import { JointSection } from './JointSection';
import { RecentTransactions } from './RecentTransactions';

/** Each person keeps one colour on every Joint screen (never colour alone: the name is always next to it). */
export const PERSON_BG: Record<Person, string> = { a: 'bg-primary', b: 'bg-secondary' };
export const PERSON_TONE: Record<Person, BarTone> = { a: 'primary', b: 'secondary' };

/**
 * The Joint profile's Overview (design C3) — made to be read by someone who
 * does not follow charts: one big sentence, three numbers with a plain note,
 * what lies ahead and what is coming up. The money concepts are the same as in
 * Personal; every figure comes from the backend (services/joint.py → household,
 * the Joint dashboard's vs_usual and upcoming bills, the bills calendar and the
 * Joint plan's forecast ranges).
 */
export function JointOverview({ year }: { year: number }) {
  const month = useUi((s) => s.selectedMonth);
  const { data, error, isLoading } = useJointHousehold(year, month);
  const dash = useDashboard(year, month).data;
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error} />;

  return (
    <div className="space-y-5">
      <Headline data={data} dash={dash} />
      <Tiles data={data} dash={dash} />
      <WorthALook year={year} month={data.month} />
      <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] items-start gap-5">
        <JointLookingAhead />
        <ComingUp dash={dash} />
      </div>
      <RecentTransactions year={year} month={data.month} monthName={data.month_name} joint limit={5} />
      <WhoPays data={data} />
      <div className="grid grid-cols-12 items-start gap-5">
        <SpentOn data={data} />
        <div className="col-span-5 space-y-5">
          <Card title="The last months" subtitle="Green is what we put in, blue is what we spent.">
            {data.months.length ? <JointMonthsChart rows={data.months} /> : <EmptyState title="No months recorded yet" />}
          </Card>
          <OurGoals data={data} />
        </div>
      </div>
      <JointSection year={year} month={data.month} />
    </div>
  );
}

/** "This month we kept 412 €." and how that compares with a usual month (backend vs_usual.kept). */
function Headline({ data, dash }: { data: JointHousehold; dash?: Dashboard }) {
  const kept = data.money.kept;
  const v = dash?.vs_usual.kept;
  const cmp = v && v.direction && v.diff !== null
    ? v.direction === 'same'
      ? { arrow: '=', tone: 'text-ink-soft', text: 'That’s about the same as in a usual month.' }
      : v.direction === 'up'
        ? { arrow: '▲', tone: 'text-positive', text: `That’s ${fmtMoney(v.diff, { round: true })} more than in a usual month.` }
        : { arrow: '▼', tone: 'text-negative', text: `That’s ${fmtMoney(-v.diff, { round: true })} less than in a usual month.` }
    : null;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-body font-medium text-ink-soft">Our shared money · {data.month_name} {data.year}</span>
      <h1 className="num text-page-title text-ink" data-testid="joint-kept">
        {kept >= 0
          ? `This month we kept ${fmtMoney(kept, { round: true })}.`
          : `This month ${fmtMoney(-kept, { round: true })} more went out than came in.`}
      </h1>
      {cmp && (
        <span className="num flex items-baseline gap-1.5 text-body text-ink-soft">
          <span aria-hidden className={cmp.tone}>{cmp.arrow}</span>{cmp.text}
        </span>
      )}
    </div>
  );
}

function Tiles({ data, dash }: { data: JointHousehold; dash?: Dashboard }) {
  const { pot, money } = data;
  const cal = useBillsCalendar(data.year, data.month).data;
  const upcoming = dash?.upcoming;
  const out = dash?.vs_usual.cash_out;
  const unpaid = (cal?.bills ?? []).filter((b) => !b.paid).length;

  const potNote = pot.negative
    ? 'Below zero — more went out than came in.'
    : !upcoming || upcoming.items.length === 0
      ? pot.earmarked > 0 ? `${fmtMoney(pot.earmarked, { round: true })} of it is saved for our goals.` : 'What is in our shared account right now.'
      : upcoming.all_ready ? 'Enough for the bills coming up.' : 'Not enough yet for all the bills coming up.';

  const spentNote = out && out.direction && out.diff !== null
    ? out.direction === 'same'
      ? 'About the same as usual.'
      : `About ${fmtMoney(out.direction === 'up' ? out.diff : -out.diff, { round: true })} ${out.direction === 'up' ? 'more' : 'less'} than usual.`
    : money.planned > 0 ? `Of ${fmtMoney(money.planned, { round: true })} we planned.` : 'Nothing planned for this month yet.';

  const billsNote = !cal
    ? undefined
    : cal.bills.length === 0
      ? 'No regular bills this month.'
      : unpaid === 0 ? 'All of this month’s bills are paid.' : `${unpaid} bill${unpaid === 1 ? '' : 's'} left this month.`;

  return (
    <div className="grid grid-cols-3 gap-4" data-testid="joint-tiles">
      <KpiTile label="In our shared account" icon={<PiggyBank size={16} />} value={fmtMoney(pot.balance, { round: true })}
        tone={pot.negative ? 'negative' : 'neutral'} alert={pot.negative} meta={potNote} />
      <KpiTile label="Spent together this month" icon={<ArrowUpRight size={16} />} value={fmtMoney(money.spent, { round: true })}
        meta={spentNote} />
      <KpiTile label="Bills still to pay" icon={<CalendarClock size={16} />} value={cal ? fmtMoney(cal.total_due, { round: true }) : '—'}
        meta={billsNote} />
    </div>
  );
}

/** Plain-English "Worth a look" — only when a variable budget needs a look this month. */
function WorthALook({ year, month }: { year: number; month: number }) {
  const a = useAttention(year, month).data;
  const setTab = useUi((s) => s.setTab);
  if (!a || a.status !== 'problem' || !a.category) return null;
  const days = `${a.days_left} day${a.days_left === 1 ? '' : 's'}`;
  const sentence = a.reason === 'over'
    ? <>{a.category} is over this month’s plan: <b>{fmtMoney(a.over ?? 0, { round: true })} more than planned.</b></>
    : a.reason === 'pace'
      ? <>{a.category} is on its way over this month’s plan: <b>{fmtMoney(a.left ?? 0, { round: true })} left for {days}.</b></>
      : <>{a.category} is close to this month’s plan: <b>{fmtMoney(a.left ?? 0, { round: true })} left for {days}.</b></>;
  const kind = a.reason === 'over' ? 'negative' : 'warning';
  return (
    <div className={`flex flex-wrap items-center gap-3 rounded-card px-4 py-3 ${kind === 'negative' ? 'bg-negative-tint' : 'bg-warning-tint'}`}
      data-testid="attention-banner" role="status">
      <StatusBadge kind={kind}>Worth a look</StatusBadge>
      <p className="num min-w-0 flex-1 text-body text-ink">{sentence}</p>
      <button type="button" className="btn-secondary btn-sm" onClick={() => setTab('transactions')}>See what we spent</button>
    </div>
  );
}

/** Bills due soon (the Joint dashboard's upcoming list) and whether the money is there. */
function ComingUp({ dash }: { dash?: Dashboard }) {
  const up = dash?.upcoming;
  const items = up?.items ?? [];
  return (
    <Card title="Coming up" testId="joint-coming-up">
      {!up ? (
        <Loading />
      ) : items.length === 0 ? (
        <p className="py-2 text-body text-ink-soft">No bills in the next {up.days} days.</p>
      ) : (
        <>
          <ul className="divide-y divide-line">
            {items.map((b) => (
              <li key={`${b.bill_id}-${b.due}`} className="grid grid-cols-[64px_minmax(0,1fr)_auto] items-center gap-x-3 py-2.5 text-body">
                <span className="num text-ink-soft">{fmtDate(b.due, { short: true })}</span>
                <span className="min-w-0 truncate text-ink">{b.name}{b.overdue && <span className="text-negative"> · late</span>}</span>
                <span className="num text-ink">{fmtMoney(b.amount, { round: true })}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3">
            {up.all_ready
              ? <StatusText kind="positive">Enough money for all of these.</StatusText>
              : <StatusText kind="warning">Not enough money yet for all of these.</StatusText>}
          </div>
        </>
      )}
    </Card>
  );
}

function WhoPays({ data }: { data: JointHousehold }) {
  const { bill, split } = data;
  const [a, b] = data.people;
  const how = split.basis === 'equal'
    ? 'We split our plan half and half.'
    : `We split our plan by income: ${a.name} ${split.share_a_pct}%, ${b.name} ${split.share_b_pct}%.`;
  const plan = bill.total > 0
    ? bill.goals > 0
      ? ` This month: ${fmtMoney(bill.costs)} for our costs + ${fmtMoney(bill.goals)} for our goals = ${fmtMoney(bill.total)}.`
      : ` This month the plan is ${fmtMoney(bill.total)}.`
    : ' Nothing is planned for this month yet — add our costs in the Forecast tab.';
  const putIn = data.money.put_in > 0 ? ` So far we put in ${fmtMoney(data.money.put_in)}.` : '';
  return (
    <Card title={<span className="flex items-center gap-1.5"><Users size={15} /> Who pays what</span>} subtitle={how + plan + putIn}>
      <div className="grid grid-cols-2 gap-5" data-testid="who-pays">
        {data.people.map((p) => (
          <div key={p.person} className="rounded-lg bg-bg px-4 py-3">
            <div className="flex items-center gap-2.5">
              <span className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold text-on-primary ${PERSON_BG[p.person]}`} aria-hidden>
                {p.name.slice(0, 1).toUpperCase()}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{p.name}</div>
                <div className="text-xs text-ink-muted">pays this month</div>
              </div>
              <div className="num text-[22px] font-semibold">{fmtMoney(p.planned)}</div>
            </div>
            <div className="mt-3">
              <ProgressBar pct={p.progress} tone={p.done || (p.planned === 0 && p.paid_in > 0) ? 'positive' : PERSON_TONE[p.person]} label={`${p.name} paid in`} />
            </div>
            <div className="num mt-1.5 text-xs">
              {p.planned === 0
                ? p.paid_in > 0
                  ? <span className="flex items-center gap-1 text-ink-soft"><Check size={13} className="text-positive" /> {fmtMoney(p.paid_in)} paid in · nothing was planned this month</span>
                  : <span className="text-ink-muted">Nothing to pay in yet</span>
                : p.done
                  ? <span className="flex items-center gap-1 font-medium text-positive"><Check size={13} /> Paid in {fmtMoney(p.paid_in)}</span>
                  : p.paid_in > 0
                    ? <span className="text-ink-soft">{fmtMoney(p.paid_in)} paid in · <b className="text-ink">{fmtMoney(p.to_go)} to go</b></span>
                    : <span className="text-ink-soft"><b className="text-ink">{fmtMoney(p.to_go)}</b> still to pay in</span>}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3">
        <Hint>Money each of us sends counts when it is recorded as income “{a.category}” or “{b.category}” (Transactions tab).</Hint>
      </div>
    </Card>
  );
}

/** Plain words under each category bar. */
function barWords(status: BudgetStatus, left: number): string {
  switch (status) {
    case 'over': return `${fmtMoney(-left)} over the plan`;
    case 'warning': return `Almost used up · ${fmtMoney(left)} left`;
    case 'on_budget': return 'Right on plan';
    case 'unbudgeted': return 'Not in the plan';
    default: return `${fmtMoney(left)} left`;
  }
}

function SpentOn({ data }: { data: JointHousehold }) {
  const rows = data.categories;
  const total = data.categories_total;
  return (
    <Card className="col-span-7" title="What we spent on"
      subtitle="Each bar fills up as we spend. A full bar means the planned amount is used.">
      {rows.length === 0 ? (
        <EmptyState title="Nothing spent or planned this month">Plan our costs in the Forecast tab.</EmptyState>
      ) : (
        <ul className="space-y-3.5" data-testid="spent-on">
          {rows.map((r) => (
            <li key={r.cat}>
              <div className="flex items-baseline gap-2 text-sm">
                <span className="flex-1 truncate font-medium">{r.cat}</span>
                <span className="num">
                  <b>{fmtMoney(r.real)}</b>
                  {r.budget > 0 && <span className="text-ink-muted"> of {fmtMoney(r.budget)}</span>}
                </span>
              </div>
              <div className="mt-1">
                <ProgressBar pct={r.progress} tone={budgetBarTone(r.status)} height="h-2.5" label={`${r.cat} spent of plan`} />
              </div>
              <div className={`num mt-0.5 text-xs ${r.status === 'over' ? 'font-medium text-negative' : r.status === 'warning' ? 'text-warning' : 'text-ink-muted'}`}>
                {barWords(r.status, r.diff)}
              </div>
            </li>
          ))}
          <li className="num flex items-baseline justify-between border-t border-line pt-3 text-sm">
            <span className="font-semibold">Together</span>
            <span>
              <b>{fmtMoney(total.real)}</b> <span className="text-ink-muted">of {fmtMoney(total.budget)} planned</span>
            </span>
          </li>
          <li className="num text-body" data-testid="joint-left">
            {data.money.status === 'over'
              ? <StatusText kind="negative">{fmtMoney(-data.money.left)} over the plan</StatusText>
              : data.money.status === 'within'
                ? <StatusText kind="positive">{fmtMoney(data.money.left)} left in the plan</StatusText>
                : <span className="text-ink-soft">Plan our costs in the Forecast tab.</span>}
          </li>
        </ul>
      )}
    </Card>
  );
}

function OurGoals({ data }: { data: JointHousehold }) {
  const setTab = useUi((s) => s.setTab);
  const { rows, monthly } = data.goals;
  const [a, b] = data.people;
  return (
    <Card title={<span className="flex items-center gap-1.5"><Target size={15} /> Our goals</span>}
      subtitle={rows.length ? 'Money we save together, for something we want.' : undefined}
      action={<button className="btn-ghost btn-sm" onClick={() => setTab('forecast')}>Manage</button>}>
      {rows.length === 0 ? (
        <EmptyState title="No goals yet">Saving for a trip or a new sofa? Add it in the Forecast tab.</EmptyState>
      ) : (
        <>
          <ul className="divide-y divide-line/70" data-testid="joint-goals">
            {rows.map((g) => (
              <li key={g.id} className="py-2.5 first:pt-0">
                <div className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{g.name}</span>
                  <GoalBadge status={g.status} />
                </div>
                <div className="mt-1.5">
                  <ProgressBar pct={g.progress_pct} tone={g.status === 'met' ? 'positive' : 'secondary'} height="h-2" label={`${g.name} saved`} />
                </div>
                <div className="num mt-1 text-xs text-ink-muted">
                  <b className="text-ink">{fmtMoney(g.saved)}</b> of {fmtMoney(g.target_amount)} · by {fmtDate(g.target_date)}
                </div>
                {g.monthly !== null && g.a !== null && g.b !== null && (
                  <div className="num text-xs text-ink-soft">
                    {g.a === g.b
                      ? <>We each put in <b>{fmtMoney(g.a)}</b> a month</>
                      : <>{a.name} <b>{fmtMoney(g.a)}</b> · {b.name} <b>{fmtMoney(g.b)}</b> a month</>}
                  </div>
                )}
              </li>
            ))}
          </ul>
          {monthly.total > 0 && (
            <div className="mt-2 border-t border-line pt-2">
              <Hint>Together our goals take <b className="num text-ink">{fmtMoney(monthly.total)}</b> a month. It is already part of what each of us pays in.</Hint>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
