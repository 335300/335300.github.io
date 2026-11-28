import { Trash2 } from 'lucide-react';
import { useState } from 'react';
import {
  useAddAccount, useDeleteAccount, useDeleteRate, useNetWorth, useNetWorthHistory, useSetAccountValue, useSetRate, useYears,
} from '../../api/queries';
import { Card, EmptyState } from '../../components/ui/Card';
import { ConfirmButton } from '../../components/ui/ConfirmButton';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { Field, FieldError } from '../../components/ui/Field';
import { KpiTile, type KpiComparison } from '../../components/ui/KpiTile';
import { StatusBadge, StatusText } from '../../components/ui/StatusBadge';
import { Skeleton } from '../../components/ui/States';
import { fmtDate, fmtLocal, fmtMoney, fmtPct, fmtSigned, parseAmount, parseLocalAmount } from '../../lib/format';
import type { AccountRow, NetWorth, NetWorthChange, NetWorthHistory, NetWorthItem } from '../../lib/types';
import { NetWorthChart } from './NetWorthChart';

const KIND_WORD: Record<AccountRow['kind'], string> = {
  current: 'Current account', savings: 'Savings (Tagesgeld)', investment: 'Investments (ETF depot)', cash: 'Cash', other: 'Other',
};

const ACCOUNT_NAME_ID = 'nw-account-name';

const local = (amount: number, currency: string) => fmtLocal(amount, currency === 'PYG' ? 'Gs' : '€');

/** An amount without its sign — the sign is said in words ("more" / "less", "Up" / "Down"). */
const size = (v: number, round = true) => fmtMoney(Math.abs(v), { round });

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

/**
 * Net worth: what you own minus what you still owe, in euros. Conversions,
 * the land as asset and debt, exchange costs and the 12-month history come
 * from services/net_worth.py and services/net_worth_history.py.
 */
export function NetWorthPage() {
  const { data, isLoading, error } = useNetWorth();
  const history = useNetWorthHistory();
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error} />;

  const focusAddForm = () => {
    const input = document.getElementById(ACCOUNT_NAME_ID);
    input?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    input?.focus({ preventScroll: true });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-page-title text-ink">Net worth</h1>
          <p className="num mt-0.5 text-[13px] text-ink-soft">
            Everything you own minus what you owe{data.rate && ` · guaraníes at ${local(data.rate.per_eur, 'PYG')} per euro (${fmtDate(data.rate.date, { short: true })})`}
          </p>
        </div>
        <button type="button" className="btn-secondary" onClick={focusAddForm}>Add account</button>
      </div>

      <Tiles data={data} history={history.data} />
      <HistoryCard history={history.data} loading={history.isLoading} error={history.error} />

      <div className="grid grid-cols-[minmax(0,1fr)_380px] items-start gap-4">
        <ItemsCard data={data} history={history.data} />
        <div className="space-y-4">
          <RateCard data={data} />
          <AccountsCard data={data} />
        </div>
      </div>
      <ExchangeCard data={data} />
    </div>
  );
}

function Tiles({ data, history }: { data: NetWorth; history?: NetWorthHistory }) {
  const vs = history?.vs_previous_month ?? null;
  const points = history?.points ?? [];
  const previous = points.length > 1 ? points[points.length - 2].label : null;
  const since = previous ? `at the end of ${previous}` : 'at the end of last month';
  const comparison: KpiComparison | undefined = vs === null ? undefined : {
    direction: vs > 0 ? 'up' : vs < 0 ? 'down' : 'same',
    tone: vs > 0 ? 'good' : vs < 0 ? 'bad' : 'neutral',
    text: vs === 0 ? `The same as ${since}` : `${size(vs)} ${vs > 0 ? 'more' : 'less'} than ${since}`,
  };
  const ownCount = data.items.filter((i) => i.side === 'own').length;

  return (
    <div className="grid grid-cols-[minmax(0,1.3fr)_repeat(3,minmax(0,1fr))] gap-4">
      <KpiTile variant="hero" label="Net worth" value={fmtMoney(data.net_worth, { round: true })} testId="kpi-net-worth"
        tone={data.net_worth < 0 ? 'negative' : 'neutral'} comparison={comparison}
        help="What you own minus what you owe, in euros. Amounts in guaraníes use the exchange rate you entered."
        meta={data.missing_rate.length
          ? <StatusText kind="warning">{data.missing_rate.join(', ')} not counted — enter an exchange rate</StatusText>
          : undefined} />
      <KpiTile label="You own" value={fmtMoney(data.own, { round: true })} meta={ownCount === 1 ? 'In 1 place' : `In ${ownCount} accounts and assets`} />
      <KpiTile label="You owe" value={data.owe ? `−${fmtMoney(data.owe, { round: true })}` : fmtMoney(0, { round: true })}
        meta={data.owe ? 'Instalments still to pay' : 'Nothing left to pay'} />
      <KpiTile label="Held in guaraníes" value={fmtMoney(data.in_pyg, { round: true })}
        meta={data.in_pyg_pct !== null
          ? `${fmtPct(data.in_pyg_pct)} of your net worth moves with the rate`
          : data.rate ? `At ${local(data.rate.per_eur, 'PYG')} per euro` : 'No exchange rate yet'} />
    </div>
  );
}

/** "Up 9,275 € in 12 months — about 9 of every 10 euros came from what you saved; …" Words only; the figures are the backend's. */
function changeSentence(c: NetWorthChange): string {
  const months = plural(c.months, 'month');
  const head = c.total > 0 ? `Up ${size(c.total)} in ${months}` : c.total < 0 ? `Down ${size(c.total)} in ${months}` : `No change in ${months}`;
  let split = '';
  if (c.saved_of_10 !== null) {
    if (c.saved_of_10 >= 10) split = ' — nearly all of it came from what you saved';
    else if (c.saved_of_10 <= 0) split = ' — nearly all of it came from what you own changing in value';
    else split = ` — about ${c.saved_of_10} of every 10 euros came from what you saved; the rest from what you own changing in value`;
  }
  return `${head}${split}.`;
}

function HistoryCard({ history, loading, error }: { history?: NetWorthHistory; loading: boolean; error: unknown }) {
  return (
    <Card title="Net worth over 12 months" meta="month-end" testId="net-worth-history">
      {loading ? <Skeleton lines={5} /> : error ? <ErrorNote error={error} /> : !history?.points.length ? (
        <EmptyState title="No month-ends yet">The chart starts once your first month is recorded.</EmptyState>
      ) : (
        <>
          {history.change && (
            <p className="num mb-3 text-[15px] font-semibold leading-[21px] text-ink" data-testid="net-worth-change">
              {changeSentence(history.change)}
              {history.change.estimated && <span className="ml-1 font-normal text-ink-soft">Some months are estimated.</span>}
            </p>
          )}
          <NetWorthChart points={history.points} />
        </>
      )}
    </Card>
  );
}

/** The quiet line under an item's name: what it is and how it is valued. */
function itemKind(i: NetWorthItem, accounts: AccountRow[]): string {
  if (i.kind === 'tracked') return 'Bank account · end of your last recorded month';
  if (i.kind === 'asset') return `Asset · valued at its ${i.basis ?? 'price'}`;
  if (i.kind === 'debt') return 'Debt · instalments still to pay';
  const account = accounts.find((a) => a.id === i.account_id);
  return `${account ? KIND_WORD[account.kind] : 'Account'}${i.as_of ? ` · as of ${fmtDate(i.as_of)}` : ''}`;
}

function dotClass(i: NetWorthItem, accounts: AccountRow[]): string {
  if (i.kind === 'debt') return 'bg-line-strong';
  if (i.kind === 'asset') return 'bg-invest';
  if (i.kind === 'account' && accounts.find((a) => a.id === i.account_id)?.kind === 'investment') return 'bg-invest';
  return 'bg-chart-1';
}

function ItemsCard({ data, history }: { data: NetWorth; history?: NetWorthHistory }) {
  const rows = [...data.items.filter((i) => i.side === 'own'), ...data.items.filter((i) => i.side === 'owe')];
  const vs = history?.vs_previous_month ?? null;
  return (
    <Card title="What makes it up" bodyClassName="!px-0" meta={data.rate ? `guaraníes at ${local(data.rate.per_eur, 'PYG')} per euro` : undefined}>
      <table className="data-table" data-testid="net-worth-items">
        <thead>
          <tr><th className="pl-5">Account</th><th className="text-right">In its currency</th><th className="pr-5 text-right">In euros</th></tr>
        </thead>
        <tbody>
          {rows.map((i) => (
            <tr key={`${i.kind}-${i.name}`}>
              <td className="cell-wrap py-1.5 pl-5">
                <span className="flex items-center gap-2.5">
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-[3px] ${dotClass(i, data.accounts)}`} aria-hidden />
                  <span className="flex min-w-0 flex-col">
                    <span className="font-medium">{i.name}</span>
                    <span className="text-label text-ink-soft">{itemKind(i, data.accounts)}</span>
                  </span>
                </span>
              </td>
              <td className="cell-num text-ink-soft">{i.currency !== 'EUR' ? local(i.amount_local, i.currency) : '—'}</td>
              <td className="cell-num pr-5 font-medium">
                {i.eur === null ? <StatusText kind="warning">No rate</StatusText> : i.side === 'owe' ? `−${fmtMoney(i.eur)}` : fmtMoney(i.eur)}
              </td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan={3} className="pl-5 text-ink-muted">Nothing here yet.</td></tr>}
        </tbody>
        <tfoot>
          <tr>
            <td className="pl-5">
              Net worth
              {vs !== null && (
                <span className="num ml-2 font-medium text-ink-soft">
                  <span aria-hidden className={vs > 0 ? 'text-positive' : vs < 0 ? 'text-negative' : ''}>{vs > 0 ? '▲' : vs < 0 ? '▼' : '='}</span>{' '}
                  {fmtSigned(vs)} since last month-end
                </span>
              )}
            </td>
            <td />
            <td className="cell-num pr-5">{fmtMoney(data.net_worth)}</td>
          </tr>
        </tfoot>
      </table>
    </Card>
  );
}

function RateCard({ data }: { data: NetWorth }) {
  const today = useYears().data?.today ?? new Date().toISOString().slice(0, 10);
  const setRate = useSetRate();
  const delRate = useDeleteRate();
  const [rate, setRateText] = useState('');
  const [date, setDate] = useState(today);
  const parsed = parseAmount(rate);
  const badNumber = rate.trim() !== '' && (parsed === null || parsed <= 0);
  const valid = parsed !== null && parsed > 0 && date;
  return (
    <Card title="Exchange rate">
      <form className="space-y-3" onSubmit={(e) => {
        e.preventDefault();
        if (valid) setRate.mutate({ currency: 'PYG', per_eur: parsed!, date }, { onSuccess: () => setRateText('') });
      }}>
        <div className="grid grid-cols-2 gap-3">
          <Field id="nw-rate" label="Guaraníes per euro" error={badNumber ? 'Use a number, e.g. 7000' : undefined}>
            <input id="nw-rate" className={`input num text-right ${badNumber ? 'input-error' : ''}`} inputMode="decimal" placeholder="e.g. 7000"
              value={rate} onChange={(e) => setRateText(e.target.value)} aria-invalid={badNumber} aria-describedby={badNumber ? 'nw-rate-error' : undefined} />
          </Field>
          <Field id="nw-rate-date" label="Rate date">
            <input id="nw-rate-date" className="input num" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="num text-label text-ink-soft" data-testid="current-rate">
            {data.rate ? <>1 € = <b className="font-semibold text-ink">{local(data.rate.per_eur, 'PYG')}</b> · saved {fmtDate(data.rate.date, { short: true })}</> : 'No rate entered yet.'}
          </span>
          <button className="btn-primary" aria-label="Save rate" disabled={!valid || setRate.isPending}>Save rate</button>
        </div>
      </form>
      {data.rates.length > 1 && (
        <ul className="num mt-3 max-h-28 overflow-y-auto border-t border-line pt-2 text-label text-ink-soft" aria-label="Earlier rates">
          {data.rates.map((r) => (
            <li key={`${r.currency}-${r.date}`} className="group flex h-6 items-center justify-between">
              <span>{fmtDate(r.date)}</span>
              <span className="flex items-center gap-1">{local(r.per_eur, 'PYG')}
                <button type="button" className="btn-icon h-6 opacity-0 focus:opacity-100 group-hover:opacity-100" aria-label={`Delete rate ${r.date}`}
                  onClick={() => delRate.mutate({ currency: r.currency, date: r.date })}><Trash2 size={12} /></button>
              </span>
            </li>
          ))}
        </ul>
      )}
      <ErrorNote error={setRate.error || delRate.error} />
    </Card>
  );
}

function AccountsCard({ data }: { data: NetWorth }) {
  const add = useAddAccount();
  const del = useDeleteAccount();
  const [name, setName] = useState('');
  const [kind, setKind] = useState<AccountRow['kind']>('savings');
  const [currency, setCurrency] = useState<'EUR' | 'PYG'>('EUR');
  return (
    <Card title="Other accounts" meta="not in the bank import">
      {!data.accounts.length ? (
        <EmptyState title="No other accounts yet">Add your Tagesgeld, ETF depot or cash.</EmptyState>
      ) : (
        <ul className="divide-y divide-line">
          {data.accounts.map((a) => <AccountItem key={a.id} account={a} onDelete={() => del.mutate(a.id)} />)}
        </ul>
      )}
      <form className="mt-3 space-y-2 rounded-lg border border-line bg-bg p-3" onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) add.mutate({ name: name.trim(), kind, currency, notes: '' }, { onSuccess: () => setName('') });
      }}>
        <Field id={ACCOUNT_NAME_ID} label="Account name">
          <input id={ACCOUNT_NAME_ID} className="input" placeholder="For example: Tagesgeld" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] gap-2">
          <Field id="nw-account-kind" label="Account kind">
            <select id="nw-account-kind" className="input" value={kind} onChange={(e) => setKind(e.target.value as AccountRow['kind'])}>
              {Object.entries(KIND_WORD).map(([k, w]) => <option key={k} value={k}>{w}</option>)}
            </select>
          </Field>
          <Field id="nw-account-currency" label="Account currency">
            <select id="nw-account-currency" className="input" value={currency} onChange={(e) => setCurrency(e.target.value as 'EUR' | 'PYG')}>
              <option value="EUR">Euro (€)</option>
              <option value="PYG">Guaraní (Gs)</option>
            </select>
          </Field>
        </div>
        <div className="flex justify-end">
          <button className="btn-primary" aria-label="Add account" disabled={!name.trim() || add.isPending}>Add account</button>
        </div>
      </form>
      <ErrorNote error={add.error || del.error} />
    </Card>
  );
}

function AccountItem({ account, onDelete }: { account: AccountRow; onDelete: () => void }) {
  const today = useYears().data?.today ?? new Date().toISOString().slice(0, 10);
  const setValue = useSetAccountValue();
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(today);
  const parsed = account.currency === 'PYG' ? parseLocalAmount(amount) : parseAmount(amount);
  const badNumber = amount.trim() !== '' && parsed === null;
  const last = account.values[account.values.length - 1];
  const errorId = `nw-value-${account.id}-error`;
  return (
    <li className="group py-2.5 text-[13px]">
      <div className="flex items-center gap-2">
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-medium">{account.name}</span>
          <span className="num text-label text-ink-soft">
            {KIND_WORD[account.kind]} · {account.currency === 'PYG' ? 'guaraníes' : 'euros'}
            {last ? ` · ${fmtDate(last.date, { short: true })}` : ''}
            {account.values.length > 1 && ` · ${account.values.length} values`}
          </span>
        </span>
        <span className="num shrink-0 text-right">{last ? local(last.amount, account.currency) : <span className="text-ink-muted">no value yet</span>}</span>
        <span className="shrink-0 opacity-0 focus-within:opacity-100 group-hover:opacity-100 has-[[role=group]]:opacity-100">
          <ConfirmButton compact label="Delete…" question={`Delete ${account.name}${account.values.length ? ' and its values' : ''}?`}
            onConfirm={onDelete} ariaLabel={`Delete account ${account.name}`} />
        </span>
      </div>
      <form className="mt-1.5 flex gap-2" onSubmit={(e) => {
        e.preventDefault();
        if (parsed !== null) setValue.mutate({ id: account.id, body: { date, amount: parsed } }, { onSuccess: () => setAmount('') });
      }}>
        <input className={`input h-7 num text-right ${badNumber ? 'input-error' : ''}`} inputMode="decimal" placeholder={`Value in ${account.currency === 'PYG' ? 'Gs' : '€'}`}
          aria-label={`Value of ${account.name}`} aria-invalid={badNumber} aria-describedby={badNumber ? errorId : undefined}
          value={amount} onChange={(e) => setAmount(e.target.value)} />
        <input className="input h-7 w-36 num" type="date" aria-label={`Date of the value of ${account.name}`} value={date} onChange={(e) => setDate(e.target.value)} />
        <button className="btn-secondary h-7" disabled={parsed === null || setValue.isPending}>Update</button>
      </form>
      {badNumber && <FieldError id={errorId}>Use a number, e.g. 1000</FieldError>}
      <ErrorNote error={setValue.error} />
    </li>
  );
}

function ExchangeCard({ data }: { data: NetWorth }) {
  const ex = data.exchange;
  const latest = ex.payments[0]; // newest first (services/net_worth.py)
  return (
    <Card title="What your transfers really cost" meta="euros sent for guaraníes · compared with the rate of the day" bodyClassName="!px-0"
      footer={ex.payments.length ? <>In total, transfers cost you <b className="font-semibold text-ink">{fmtMoney(ex.total_cost)}</b> on {fmtMoney(ex.total_paid)} sent.</> : undefined}>
      {!ex.payments.length ? (
        <div className="px-5">
          <EmptyState title="No transfers with an amount in guaraníes yet">Add “Gs received” when you record a land payment (Transactions tab).</EmptyState>
        </div>
      ) : (
        <>
          <div className="num flex items-center gap-3 px-5 pb-3 text-body" data-testid="exchange-latest">
            <StatusBadge kind="info">Last transfer</StatusBadge>
            <span>
              {latest.cost_pct === null
                ? 'Your last transfer has no rate of the day to compare with yet.'
                : latest.cost_pct >= 0
                  ? <>Your last transfer lost <b className="font-semibold">{fmtPct(latest.cost_pct, 2)}</b> to the exchange rate.</>
                  : <>Your last transfer got <b className="font-semibold">{fmtPct(Math.abs(latest.cost_pct), 2)}</b> more than the rate of the day.</>}
            </span>
          </div>
          <table className="data-table" data-testid="exchange-costs">
            <thead>
              <tr>
                <th className="pl-5">Date</th><th>Payment</th><th className="text-right">Paid</th>
                <th className="text-right">Arrived</th><th className="text-right">Your rate</th>
                <th className="text-right">Rate of the day</th><th className="pr-5 text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              {ex.payments.map((p) => (
                <tr key={`${p.year}-${p.id}`}>
                  <td className="num pl-5 text-ink-soft">{fmtDate(p.date, { short: true })}</td>
                  <td className="cell-wrap">{p.desc || p.cat}</td>
                  <td className="cell-num">{fmtMoney(p.eur_paid)}</td>
                  <td className="cell-num">{local(p.foreign_amount, p.currency)}</td>
                  <td className="cell-num">{local(p.rate_got, p.currency)}</td>
                  <td className="cell-num text-ink-soft">{p.rate_reference === null ? '—' : local(p.rate_reference, p.currency)}</td>
                  <td className="cell-num pr-5">
                    {p.cost === null ? <span className="text-ink-muted">no rate</span> : <>{fmtSigned(-p.cost)} <span className="text-ink-soft">({fmtPct(p.cost_pct ?? 0, 2)})</span></>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Card>
  );
}
