import { Palmtree, Plus, ReceiptEuro, RotateCcw, Settings2, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useAddPayslip, useAddVacation, useDeletePayslip, useDeleteVacation, useIncome, useSetTypedHours } from '../../api/queries';
import { Card, EmptyState } from '../../components/ui/Card';
import { StatusIcon } from '../../components/ui/StatusBadge';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { fmtDate, fmtMoney, fmtMonthYear, fmtPct, fmtSigned, parseAmount } from '../../lib/format';
import type { CalendarRow, CalendarWarning, IncomeView, WorkMonthKind } from '../../lib/types';
import { IncomeSettingsModal } from './IncomeSettingsModal';

const KIND: Record<WorkMonthKind, { word: string; cls: string }> = {
  lecture: { word: 'Lectures', cls: 'bg-primary-tint text-primary' },
  break: { word: 'Break', cls: 'bg-secondary-tint text-secondary' },
  mixed: { word: 'Part / part', cls: 'bg-warning-tint text-warning-ink' },
  none: { word: 'No work', cls: 'bg-neutral-tint text-ink-soft' },
};

const WARNING: Record<CalendarWarning, string> = {
  no_payslips: 'Enter at least one real payslip below. Until then the app cannot work out net pay, and the forecast keeps using your salary budget.',
  no_lecture_periods: 'No lecture periods entered yet, so every month counts as a break month (full-time).',
  lecture_periods_end_early: 'Your lecture periods end before the last month shown; later months count as break months. Add the next semester in the settings.',
  no_hourly_rate: 'Set your hourly rate in the settings.',
  werkstudent_26_weeks: 'More than 26 weeks with over 20 hours of work in these 12 months. A working student may only do that for 26 weeks in 12 months — beyond it, health, care and unemployment insurance become due and net pay drops. Check your lecture periods and break hours.',
};

/**
 * The working-student income calendar: expected hours, gross and net pay per
 * month of work, and when it arrives. All figures come from the backend
 * (services/income_calendar.py).
 */
export function IncomeCalendarCard({ year, settingsOpen: openFromPage = false, onSettingsClose }: {
  year: number;
  /** The page's "Income settings" button opens the same dialog. */
  settingsOpen?: boolean;
  onSettingsClose?: () => void;
}) {
  const { data, isLoading, error } = useIncome();
  const [ownOpen, setOwnOpen] = useState(false);
  const settingsOpen = ownOpen || openFromPage;
  const closeSettings = () => { setOwnOpen(false); onSettingsClose?.(); };
  const setSettingsOpen = (v: boolean) => (v ? setOwnOpen(true) : closeSettings());
  const method = data?.calendar?.net_method === 'payslips' ? 'net pay from your payslips' : 'payroll rules, working student, tax class 1';

  return (
    <Card
      title="Income calendar"
      collapseKey="forecast-income-calendar"
      collapseLabel="Income calendar"
      meta={data?.plan ? method : undefined}
      action={data?.plan && (
        <button className="btn-secondary btn-sm" onClick={() => setSettingsOpen(true)}><Settings2 size={14} /> Settings</button>
      )}
      testId="income-calendar"
    >
      {isLoading ? <Loading /> : error ? <ErrorNote error={error} /> : !data?.plan ? (
        <EmptyState title="No income calendar yet"
          action={<button className="btn-primary btn-sm" onClick={() => setSettingsOpen(true)}>Set up the income calendar</button>}>
          Hourly rate, lecture periods and hours — then the forecast follows your real pay.
        </EmptyState>
      ) : (
        <CalendarBody data={data} />
      )}
      {settingsOpen && (
        <IncomeSettingsModal year={year} plan={data?.plan ?? null} onClose={closeSettings} />
      )}
    </Card>
  );
}

function CalendarBody({ data }: { data: IncomeView }) {
  const plan = data.plan!;
  const cal = data.calendar!;
  const rules = cal.net_method === 'tax_rules';
  const pct = (v: number | null) => (v === null ? '—' : fmtPct(v, 1));
  const lagWord = plan.contract_pay_lag ? 'the month after' : 'the same month';
  // Italic = expected: a month of work without a real payslip yet.
  const slipMonths = new Set((plan.payslips ?? []).map((p) => p.month));
  return (
    <div className="space-y-4">
      <p className="text-[13px] text-ink-soft">
        {fmtMoney(plan.hourly_rate)} an hour · {plan.hours_lecture_week} h a week in lectures, {plan.hours_break_week} h in breaks ·
        pay booked {lagWord}{plan.extra_hours_delay ? ', extra hours one month later' : ''}.
        {!plan.enabled && <b className="text-warning-ink"> Switched off — the forecast uses your salary budget.</b>}
        {plan.enabled && data.active && <span className="text-positive"> The forecast uses these figures.</span>}
      </p>
      {cal.warnings.length > 0 && (
        <ul className="space-y-1">
          {cal.warnings.map((w) => (
            <li key={w} className="flex items-start gap-2 rounded-input bg-warning-tint px-3 py-2 text-label text-warning-ink">
              <StatusIcon kind="warning" className="mt-px" /><span><b>Heads-up:</b> {WARNING[w]}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="-mx-5 overflow-x-auto">
        <table className="data-table data-table-compact [&_td:first-child]:pl-5 [&_td:last-child]:pr-5 [&_th:first-child]:pl-5 [&_th:last-child]:pr-5">
          <thead>
            <tr>
              <th>Month worked</th>
              <th>Type</th>
              <th className="text-right">Hours</th>
              <th className="text-right">Gross</th>
              {rules && <th className="text-right" title="Income tax, solidarity surcharge and church tax">Income tax</th>}
              {rules && <th className="text-right">Pension</th>}
              {rules && <th className="text-right" title="Share of gross that comes off">Off</th>}
              <th className="text-right">Net</th>
              <th>Paid in</th>
              <th className="text-right">Arrives this month</th>
            </tr>
          </thead>
          <tbody className="num">
            {cal.rows.map((r) => (
              <tr key={r.key} className={slipMonths.has(r.key) ? '' : 'italic text-ink-soft'} data-expected={slipMonths.has(r.key) ? undefined : 'true'}>
                <td>
                  {r.month_name}
                  {r.job_ends.map((name) => (
                    <span key={name} className="chip ml-1.5 not-italic">{name}: job ends</span>
                  ))}
                </td>
                <td>
                  <span className={`chip not-italic ${KIND[r.kind].cls}`}>{KIND[r.kind].word}</span>
                  {r.kind === 'mixed' && <span className="ml-1 text-label text-ink-muted">{r.lecture_days} lecture / {r.break_days} break days</span>}
                  {r.vacation_days > 0 && (
                    <span className="chip ml-1.5 bg-secondary-tint not-italic text-secondary"
                      title={r.vacation_rate !== null ? `${fmtMoney(r.vacation_rate)} a vacation day (average of the 3 months before)` : undefined}
                      data-testid={`vacation-${r.key}`}>
                      <Palmtree size={11} /> {r.vacation_days} vacation day{r.vacation_days === 1 ? '' : 's'} · {fmtMoney(r.vacation_pay)}
                    </span>
                  )}
                </td>
                <td className="cell-num not-italic"><HoursCell row={r} /></td>
                <td className="cell-num">{fmtMoney(r.gross)}</td>
                {rules && <td className="cell-num text-ink-soft">{r.income_tax === null ? '—' : fmtMoney(r.income_tax)}</td>}
                {rules && <td className="cell-num text-ink-soft">{r.pension === null ? '—' : fmtMoney(r.pension)}</td>}
                {rules && <td className="cell-num text-ink-muted" data-testid={`deducted-${r.key}`}>{pct(r.deducted_pct)}</td>}
                <td className="cell-num">{r.net === null ? '—' : fmtMoney(r.net)}</td>
                <td className="text-label text-ink-soft">
                  {r.contract_paid_in}{r.extra_paid_in && r.extra_paid_in !== r.contract_paid_in ? ` · extra ${r.extra_paid_in}` : ''}
                </td>
                <td className="cell-num">{r.received === null ? '—' : fmtMoney(r.received)}</td>
              </tr>
            ))}
          </tbody>
          {cal.total_net !== null && (
            <tfoot className="num">
              <tr>
                <td className="pl-5" colSpan={3}>12 months{cal.average_net !== null ? ` · on average ${fmtMoney(cal.average_net)} net a month` : ''}</td>
                <td className="text-right">{fmtMoney(cal.total_gross)}</td>
                {rules && <td colSpan={3} />}
                <td className="text-right">{fmtMoney(cal.total_net)}</td>
                <td colSpan={2} className="pr-5" />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      <p className="text-label text-ink-soft">Italic = expected · upright = a month with a real payslip.</p>
      <Vacations data={data} />
      {cal.refund && <Refund refund={cal.refund} />}
      <Payslips data={data} />
    </div>
  );
}

/** What the tax return may give back: more is withheld in full-time months than a year with lecture months owes. */
function Refund({ refund }: { refund: NonNullable<NonNullable<IncomeView['calendar']>['refund']> }) {
  const back = refund.refund > 0;
  return (
    <div className="flex items-start gap-3 rounded-input border border-line bg-bg px-4 py-3" data-testid="tax-refund">
      <ReceiptEuro size={16} className="mt-0.5 shrink-0 text-ink-soft" />
      <div className="text-sm">
        <p>
          <strong>Tax return {refund.year}: </strong>
          {back
            ? <>about <strong className="num text-positive">{fmtMoney(refund.refund, { round: true })}</strong> back, if you work as planned.</>
            : <>nothing to get back on these figures.</>}
        </p>
        <p className="num mt-0.5 text-label text-ink-soft">
          Withheld over the year {fmtMoney(refund.withheld, { round: true })} · tax owed on {fmtMoney(refund.gross, { round: true })} gross{' '}
          {fmtMoney(refund.owed, { round: true })}. An estimate, not tax advice; not added to the forecast.
          {refund.rules_year !== refund.year && ` ${refund.year} uses the ${refund.rules_year} tax values until the new ones are final.`}
        </p>
      </div>
    </div>
  );
}

function Payslips({ data }: { data: IncomeView }) {
  const add = useAddPayslip();
  const del = useDeletePayslip();
  const [month, setMonth] = useState('');
  const [gross, setGross] = useState('');
  const [net, setNet] = useState('');
  const g = parseAmount(gross);
  const n = parseAmount(net);
  const valid = /^\d{4}-\d{2}$/.test(month) && g !== null && g > 0 && n !== null && n > 0;
  const slips = data.plan?.payslips ?? [];
  const rules = data.calendar?.net_method === 'tax_rules';
  const checks = new Map((data.calendar?.payslip_checks ?? []).map((c) => [c.id, c]));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    add.mutate({ month, gross: g!, net: n!, note: '' }, { onSuccess: () => { setMonth(''); setGross(''); setNet(''); } });
  };

  return (
    <div className="border-t border-line pt-4">
      <h3 className="text-[13px] font-semibold">Payslips</h3>
      <ul className="mt-1 divide-y divide-line">
        {slips.map((p) => (
          <li key={p.id} className="num group flex items-center gap-3 py-1.5 text-[13px]">
            <span className="w-36">{fmtMonthYear(p.month)}</span>
            <span className="flex-1 text-ink-soft">
              gross {fmtMoney(p.gross)} → net {fmtMoney(p.net)}
              {rules && checks.get(p.id) && (
                <span className="ml-2 text-xs text-ink-muted" data-testid={`payslip-check-${p.id}`}>
                  · tax rules: {fmtMoney(checks.get(p.id)!.rules_net)} ({fmtSigned(checks.get(p.id)!.difference)} on your payslip)
                </span>
              )}
            </span>
            <button className="btn-ghost btn-sm opacity-0 group-hover:opacity-100" aria-label={`Delete payslip ${p.month}`} onClick={() => del.mutate(p.id)}>
              <Trash2 size={12} />
            </button>
          </li>
        ))}
        {!slips.length && <li className="py-1.5 text-label text-ink-soft">No payslips yet.</li>}
      </ul>
      <form onSubmit={submit} className="mt-2 flex items-end gap-2">
        <div>
          <label className="label" htmlFor="slip-month">Month worked</label>
          <input id="slip-month" type="month" className="input h-8 num" value={month} onChange={(e) => setMonth(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="slip-gross">Gross (€)</label>
          <input id="slip-gross" inputMode="decimal" className="input h-8 w-28 num" value={gross} onChange={(e) => setGross(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="slip-net">Net (€)</label>
          <input id="slip-net" inputMode="decimal" className="input h-8 w-28 num" value={net} onChange={(e) => setNet(e.target.value)} />
        </div>
        <button className="btn-secondary h-8" disabled={!valid || add.isPending}><Plus size={14} /> Add payslip</button>
      </form>
      <ErrorNote error={add.error || del.error} />
      {data.calendar?.lecture_periods_until && (
        <p className="mt-2 text-xs text-ink-muted">Lecture periods entered until {fmtDate(data.calendar.lecture_periods_until)}.</p>
      )}
    </div>
  );
}

/** The hours of a month of work: type them to set them by hand; ↺ goes back to the calendar's hours. */
function HoursCell({ row }: { row: CalendarRow }) {
  const save = useSetTypedHours();
  const shown = row.hours_typed ? String(row.hours) : '';
  const [text, setText] = useState(shown);
  useEffect(() => setText(shown), [shown]);
  const trimmed = text.trim();
  const parsed = trimmed ? parseAmount(trimmed) : null;
  const invalid = trimmed !== '' && (parsed === null || parsed < 0 || parsed > 400);

  const commit = () => {
    if (invalid) { setText(shown); return; }
    if (trimmed === shown) return;
    save.mutate({ month: row.key, hours: trimmed === '' ? null : parsed });
  };

  return (
    <span className="relative inline-block">
      {row.hours_typed && (
        <button type="button" aria-label={`Back to the calendar's hours: ${row.month_name}`}
          title={`Typed by hand — the calendar says ${row.hours_auto} h. Click: back to the calendar's hours.`}
          className="absolute left-0 top-1/2 z-10 -translate-y-1/2 rounded p-1 text-primary hover:bg-primary-tint focus:outline-none focus:ring-2 focus:ring-primary/30"
          onClick={() => save.mutate({ month: row.key, hours: null })}>
          <RotateCcw size={12} />
        </button>
      )}
      <input
        aria-label={`Hours worked ${row.month_name}`}
        title={row.hours_typed ? `Typed by hand (the calendar says ${row.hours_auto} h)` : 'From your lecture periods and weekly hours · type to change'}
        inputMode="decimal"
        value={text}
        placeholder={String(row.hours_auto)}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
        data-typed={row.hours_typed ? 'true' : undefined}
        aria-invalid={invalid || undefined}
        className={`num h-7 w-20 rounded-input border bg-transparent px-1.5 text-right text-[13px] text-ink focus:border-primary focus:outline-none focus:ring-2 focus:ring-focus-ring ${
          invalid ? 'border-negative' : 'border-transparent hover:border-line-strong'
        } ${row.hours_typed ? 'pl-6 font-medium text-ink' : 'placeholder:text-ink'}`}
      />
    </span>
  );
}

/** Paid vacation: each Monday–Friday inside is paid at the average of the 3 months before (the backend works it out). */
function Vacations({ data }: { data: IncomeView }) {
  const add = useAddVacation();
  const del = useDeleteVacation();
  const vacations = data.plan?.vacations ?? [];
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [note, setNote] = useState('');
  const valid = start !== '' && end !== '' && end >= start;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    add.mutate({ start, end, note }, { onSuccess: () => { setStart(''); setEnd(''); setNote(''); } });
  };

  return (
    <section data-testid="vacations">
      <h3 className="flex items-center gap-1.5 text-[13px] font-semibold"><Palmtree size={14} /> Vacation</h3>
      {vacations.length > 0 && (
        <ul className="mt-1 divide-y divide-line/60 text-sm">
          {vacations.map((v) => (
            <li key={v.id} className="group flex items-center gap-2 py-1">
              <span className="num">{fmtDate(v.start)}{v.end !== v.start ? ` – ${fmtDate(v.end)}` : ''}</span>
              {v.note && <span className="text-ink-muted">· {v.note}</span>}
              <button className="btn-ghost btn-sm ml-auto opacity-0 group-hover:opacity-100 focus:opacity-100"
                aria-label={`Delete vacation from ${v.start}`} onClick={() => del.mutate(v.id)}>
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit} className="mt-2 flex flex-wrap items-end gap-2">
        <div>
          <label className="label" htmlFor="vac-start">First day</label>
          <input id="vac-start" type="date" className="input h-8 num" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="vac-end">Last day</label>
          <input id="vac-end" type="date" className="input h-8 num" value={end} min={start || undefined} onChange={(e) => setEnd(e.target.value)} />
        </div>
        <div className="min-w-40 flex-1">
          <label className="label" htmlFor="vac-note">Note (optional)</label>
          <input id="vac-note" className="input h-8" maxLength={80} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        <button className="btn-secondary h-8" disabled={!valid || add.isPending}><Plus size={14} /> Add vacation</button>
      </form>
      <ErrorNote error={add.error || del.error} />
    </section>
  );
}
