import { useState } from 'react';
import { useSetup } from '../api/queries';
import { MONTHS, parseAmount } from '../lib/format';
import type { YearsResponse } from '../lib/types';
import { ErrorNote } from './ui/Feedback';
import { FieldError } from './ui/Field';

/** First run on a fresh install: where do you start from? */
export function SetupCard({ years }: { years: YearsResponse }) {
  const setup = useSetup();
  const [year, setYear] = useState(years.current_year);
  const [firstMonth, setFirstMonth] = useState(years.current_month);
  const [balance, setBalance] = useState('');
  const [starter, setStarter] = useState(true);
  const amount = parseAmount(balance || '0');

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (amount === null) return;
    setup.mutate({ year, opening_balance: amount, start_month: firstMonth - 1, starter_categories: starter });
  };

  return (
    <div className="mx-auto mt-10 max-w-lg">
      <form onSubmit={submit} className="rounded-card border border-line bg-surface p-7 shadow-card">
        <h1 className="text-page-title">Welcome to Personal Centwise</h1>
        <p className="mt-1.5 text-body text-ink-soft">
          Two quick questions to set your starting point. Everything stays on this Mac, and you can change both later in
          the Forecast tab.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="setup-month">I start tracking in</label>
            <select id="setup-month" className="input" value={firstMonth} onChange={(e) => setFirstMonth(Number(e.target.value))}>
              {MONTHS.map((m, i) => (
                <option key={m} value={i}>{m}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="setup-year">of</label>
            <input id="setup-year" type="number" className="input num" value={year} min={2000} max={2100}
              onChange={(e) => setYear(Number(e.target.value))} />
          </div>
        </div>

        <div className="mt-4">
          <label className="label" htmlFor="setup-balance">Money I had at the start of {MONTHS[firstMonth]}</label>
          <div className="relative">
                        <input id="setup-balance" inputMode="decimal" className={`input num pr-7 ${amount === null ? 'input-error' : ''}`} placeholder="0,00" value={balance}
              onChange={(e) => setBalance(e.target.value)} />
            <span aria-hidden className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-body text-ink-soft">€</span>
          </div>
          <p className="mt-1.5 text-label text-ink-soft">All accounts and cash together. A rough number is fine.</p>
          {amount === null && <FieldError>Please enter a number, e.g. 1.250,00</FieldError>}
        </div>

        <label className="mt-5 flex items-start gap-2.5 rounded-lg border border-line p-3 text-body">
          <input type="checkbox" className="mt-0.5 accent-[rgb(var(--c-primary))]" checked={starter} onChange={(e) => setStarter(e.target.checked)} />
          <span>
            <span className="font-medium">Start with common categories</span>
            <span className="block text-label text-ink-soft">Rent, Groceries, Salary and a few more — rename or delete any of them later.</span>
          </span>
        </label>

        <ErrorNote error={setup.error} />
        <button type="submit" className="btn-primary mt-6 w-full" disabled={setup.isPending || amount === null}>
          Get started
        </button>
      </form>
    </div>
  );
}
