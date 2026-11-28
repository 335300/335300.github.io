import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useCategories, useSaveIncomeSettings } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { Modal } from '../../components/ui/Modal';
import { parseAmount } from '../../lib/format';
import type { IncomePlan, IncomeSettings } from '../../lib/types';

interface ScenarioDraft {
  name: string;
  job_end: string;
  health: string;
  salary: string;
}

const MAX_SCENARIOS = 3;

const num = (v: number | null | undefined) => (v === null || v === undefined ? '' : String(v));

/**
 * Settings of the income calendar. This form only collects what you type; the
 * backend validates it and does all the arithmetic.
 */
export function IncomeSettingsModal({ year, plan, onClose }: { year: number; plan: IncomePlan | null; onClose: () => void }) {
  const save = useSaveIncomeSettings();
  const categories = useCategories(year);
  const [enabled, setEnabled] = useState(plan?.enabled ?? true);
  const [rate, setRate] = useState(num(plan?.hourly_rate || null));
  const [lectureHours, setLectureHours] = useState(num(plan?.hours_lecture_week ?? 20));
  const [breakHours, setBreakHours] = useState(num(plan?.hours_break_week ?? 40));
  const [periods, setPeriods] = useState(plan?.lecture_periods ?? [{ start: '', end: '' }]);
  const [salaryCat, setSalaryCat] = useState(plan?.salary_category ?? 'Salary');
  const [healthCat, setHealthCat] = useState(plan?.health_category ?? '');
  const [lag, setLag] = useState(plan?.contract_pay_lag ?? 1);
  const [payDay, setPayDay] = useState(plan?.pay_day ?? -1);
  const [extraDelay, setExtraDelay] = useState(plan?.extra_hours_delay ?? 1);
  const [netMethod, setNetMethod] = useState<IncomeSettings['net_method']>(plan?.net_method ?? 'tax_rules');
  const [church, setChurch] = useState<IncomeSettings['church_tax_rate']>(plan?.church_tax_rate ?? 0);
  const [scenarios, setScenarios] = useState<ScenarioDraft[]>(
    plan?.scenarios.length
      ? plan.scenarios.map((s) => ({ name: s.name, job_end: s.job_end, health: num(s.health_insurance_monthly), salary: num(s.new_net_salary) }))
      : [{ name: 'Best case', job_end: '', health: '', salary: '' }, { name: 'Worst case', job_end: '', health: '', salary: '' }],
  );

  const rateValue = parseAmount(rate);
  const valid = rateValue !== null && rateValue > 0 && lectureHours !== '' && breakHours !== '';

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    const body: IncomeSettings = {
      enabled,
      hourly_rate: rateValue!,
      hours_lecture_week: Number(lectureHours),
      hours_break_week: Number(breakHours),
      lecture_periods: periods.filter((p) => p.start && p.end),
      salary_category: salaryCat,
      contract_pay_lag: lag,
      extra_hours_delay: extraDelay,
      health_category: healthCat,
      net_method: netMethod,
      church_tax_rate: church,
      pay_day: payDay,
      // A scenario without an end date is left out.
      scenarios: scenarios
        .filter((s) => s.name.trim() && s.job_end)
        .map((s) => ({
          name: s.name.trim(),
          job_end: s.job_end,
          health_insurance_monthly: s.health.trim() ? parseAmount(s.health) : null,
          new_net_salary: s.salary.trim() ? parseAmount(s.salary) : null,
        })),
    };
    save.mutate(body, { onSuccess: onClose });
  };

  const setPeriod = (i: number, field: 'start' | 'end', value: string) =>
    setPeriods((all) => all.map((p, j) => (j === i ? { ...p, [field]: value } : p)));
  const setScenario = (i: number, field: keyof ScenarioDraft, value: string) =>
    setScenarios((all) => all.map((s, j) => (j === i ? { ...s, [field]: value } : s)));

  return (
    <Modal title="Income calendar settings" open onClose={onClose} width="lg">
      <form onSubmit={submit} className="space-y-5 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Use the income calendar in the forecast
        </label>

        <section className="grid grid-cols-3 gap-3">
          <div>
            <label className="label" htmlFor="inc-rate">Hourly rate (€)</label>
            <input id="inc-rate" inputMode="decimal" className="input num" placeholder="22" value={rate} onChange={(e) => setRate(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="inc-lecture">Hours a week in lectures</label>
            <input id="inc-lecture" type="number" min={0} max={60} step="0.5" className="input num" value={lectureHours} onChange={(e) => setLectureHours(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="inc-break">Hours a week in breaks</label>
            <input id="inc-break" type="number" min={0} max={60} step="0.5" className="input num" value={breakHours} onChange={(e) => setBreakHours(e.target.value)} />
          </div>
        </section>

        <section className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="inc-net">Net pay is worked out</label>
            <select id="inc-net" className="input" value={netMethod} onChange={(e) => setNetMethod(e.target.value as IncomeSettings['net_method'])}>
              <option value="tax_rules">By German tax rules (working student, tax class 1)</option>
              <option value="payslips">From my payslips (net-to-gross ratio)</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="inc-church">Church tax</label>
            <select id="inc-church" className="input" value={church} disabled={netMethod !== 'tax_rules'}
              onChange={(e) => setChurch(Number(e.target.value) as IncomeSettings['church_tax_rate'])}>
              <option value={0}>None (not a church member)</option>
              <option value={8}>8 % (Baden-Württemberg, Bavaria)</option>
              <option value={9}>9 % (other states)</option>
            </select>
          </div>
          <p className="col-span-2 text-xs text-ink-muted">
            The tax rules take off income tax for each month as if that month&rsquo;s pay ran all year, plus pension insurance (9.3&nbsp;%,
            less on months under €2,000). As a working student you pay no health, care or unemployment insurance through the job.
          </p>
        </section>

        <section>
          <h3 className="font-semibold">Lecture periods</h3>
          <p className="text-xs text-ink-muted">First and last day of each Vorlesungszeit. Every other weekday counts as a break day.</p>
          <ul className="mt-2 space-y-1.5">
            {periods.map((p, i) => (
              <li key={i} className="flex items-center gap-2">
                <input type="date" className="input h-8 num" aria-label={`Lecture period ${i + 1} first day`} value={p.start} onChange={(e) => setPeriod(i, 'start', e.target.value)} />
                <span className="text-ink-muted">to</span>
                <input type="date" className="input h-8 num" aria-label={`Lecture period ${i + 1} last day`} value={p.end} onChange={(e) => setPeriod(i, 'end', e.target.value)} />
                <button type="button" className="btn-ghost btn-sm" aria-label={`Remove lecture period ${i + 1}`} onClick={() => setPeriods((all) => all.filter((_, j) => j !== i))}><Trash2 size={13} /></button>
              </li>
            ))}
          </ul>
          <button type="button" className="btn-secondary btn-sm mt-2" onClick={() => setPeriods((all) => [...all, { start: '', end: '' }])}>
            <Plus size={13} /> Add a lecture period
          </button>
        </section>

        <section className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="inc-lag">Pay is booked</label>
            <select id="inc-lag" className="input" value={lag} onChange={(e) => setLag(Number(e.target.value))}>
              <option value={0}>In the month worked</option>
              <option value={1}>In the month after (paid at month end)</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="inc-pay-day">Pay arrives on the account</label>
            <select id="inc-pay-day" className="input" value={payDay} onChange={(e) => setPayDay(Number(e.target.value))}>
              <option value={-1}>The working day before the last working day</option>
              <option value={0}>Last working day of the month</option>
              {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>On day {d} (earlier on a weekend)</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="inc-extra">Extra hours (above the lecture hours)</label>
            <select id="inc-extra" className="input" value={extraDelay} onChange={(e) => setExtraDelay(Number(e.target.value))}>
              <option value={0}>Paid with the normal pay</option>
              <option value={1}>Paid one month later</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="inc-salary">Salary category it replaces</label>
            <input id="inc-salary" className="input" list="inc-income-cats" value={salaryCat} onChange={(e) => setSalaryCat(e.target.value)} />
            <datalist id="inc-income-cats">{categories.data?.income.map((c) => <option key={c.name} value={c.name} />)}</datalist>
          </div>
          <div>
            <label className="label" htmlFor="inc-health">Health insurance category</label>
            <input id="inc-health" className="input" list="inc-expense-cats" placeholder="e.g. Insurance" value={healthCat} onChange={(e) => setHealthCat(e.target.value)} />
            <datalist id="inc-expense-cats">{categories.data?.expense.map((c) => <option key={c.name} value={c.name} />)}</datalist>
          </div>
        </section>

        <section>
          <h3 className="font-semibold">Graduation scenarios</h3>
          <p className="text-xs text-ink-muted">
            Each one is a line on the forecast chart. After its end date the student job stops and the health insurance
            costs the amount you enter. A new net salary is optional. Leave the date empty to skip a scenario.
          </p>
          <div className="mt-2 grid grid-cols-[1.2fr_1fr_1fr_1fr_auto] gap-2 text-xs text-ink-muted">
            <span>Name</span><span>Last day of the student job</span><span>Health insurance / month (€)</span><span>New net salary / month (€)</span><span />
          </div>
          <ul className="space-y-1.5">
            {scenarios.map((s, i) => (
              <li key={i} className="grid grid-cols-[1.2fr_1fr_1fr_1fr_auto] items-center gap-2">
                <input className="input h-8" aria-label={`Scenario ${i + 1} name`} value={s.name} onChange={(e) => setScenario(i, 'name', e.target.value)} />
                <input type="date" className="input h-8 num" aria-label={`Scenario ${i + 1} end date`} value={s.job_end} onChange={(e) => setScenario(i, 'job_end', e.target.value)} />
                <input inputMode="decimal" className="input h-8 num" aria-label={`Scenario ${i + 1} health insurance`} value={s.health} onChange={(e) => setScenario(i, 'health', e.target.value)} />
                <input inputMode="decimal" className="input h-8 num" aria-label={`Scenario ${i + 1} new salary`} placeholder="optional" value={s.salary} onChange={(e) => setScenario(i, 'salary', e.target.value)} />
                <button type="button" className="btn-ghost btn-sm" aria-label={`Remove scenario ${i + 1}`} onClick={() => setScenarios((all) => all.filter((_, j) => j !== i))}><Trash2 size={13} /></button>
              </li>
            ))}
          </ul>
          {scenarios.length < MAX_SCENARIOS && (
            <button type="button" className="btn-secondary btn-sm mt-2" onClick={() => setScenarios((all) => [...all, { name: '', job_end: '', health: '', salary: '' }])}>
              <Plus size={13} /> Add a scenario
            </button>
          )}
        </section>

        <ErrorNote error={save.error} />
        <div className="flex justify-end gap-2 border-t border-line pt-3">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={!valid || save.isPending}>Save settings</button>
        </div>
      </form>
    </Modal>
  );
}
