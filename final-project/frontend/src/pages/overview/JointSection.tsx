import { Handshake, Scale, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useAddSettlement, useAddShared, useDeleteSettlement, useDeleteShared, useJoint, useSaveFairShare, useYears } from '../../api/queries';
import { Card } from '../../components/ui/Card';
import { Field } from '../../components/ui/Field';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { fmtDate, fmtMoney, parseAmount } from '../../lib/format';
import type { JointView, Person } from '../../lib/types';

/**
 * Joint profile only: the fair-share calculator and the settle-up balance.
 * Every percentage and amount comes from the backend (services/joint.py).
 */
export function JointSection({ year, month }: { year: number; month: number }) {
  const { data, isLoading, error } = useJoint(year, month);
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error} />;
  return (
    <>
      <div className="flex items-baseline gap-3 pt-1">
        <h2 className="text-[13px] font-semibold uppercase tracking-wide text-ink-soft">Between us</h2>
        <p className="text-xs text-ink-muted">Our names, how we split, and who owes whom.</p>
      </div>
      <div className="grid grid-cols-12 gap-5">
        <FairShareCard data={data} />
        <SettleUpCard data={data} />
      </div>
    </>
  );
}

function FairShareCard({ data }: { data: JointView }) {
  const save = useSaveFairShare();
  const fs = data.fair_share;
  const [nameA, setNameA] = useState(fs.name_a);
  const [nameB, setNameB] = useState(fs.name_b);
  const [incomeA, setIncomeA] = useState(fs.income_a === null ? '' : String(fs.income_a));
  const [incomeB, setIncomeB] = useState(fs.income_b === null ? '' : String(fs.income_b));
  useEffect(() => { setNameA(fs.name_a); setNameB(fs.name_b); }, [fs.name_a, fs.name_b]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    save.mutate({
      name_a: nameA.trim() || 'Josu', name_b: nameB.trim() || 'Isa',
      income_a: incomeA.trim() ? parseAmount(incomeA) : null, income_b: incomeB.trim() ? parseAmount(incomeB) : null,
    });
  };

  return (
    <Card className="col-span-5" title={<span className="flex items-center gap-1.5"><Scale size={15} /> How we split</span>}
      subtitle="Each of us pays a part of the shared costs, in proportion to what we earn. Until both incomes are filled in, we split 50/50.">
      <div className="mb-3 grid grid-cols-2 gap-3 text-center" data-testid="fair-share">
        {([['a', fs.name_a, fs.share_a_pct, fs.amount_a], ['b', fs.name_b, fs.share_b_pct, fs.amount_b]] as const).map(([key, name, pct, amount]) => (
          <div key={key} className="rounded-lg bg-bg px-3 py-2">
            <div className="text-xs text-ink-soft">{name}</div>
            <div className="num text-xl font-semibold">{pct}%</div>
            {amount !== null && <div className="num text-xs text-ink-muted">≈ {fmtMoney(amount)} in a usual month</div>}
          </div>
        ))}
      </div>
      <form onSubmit={submit} className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 border-t border-line pt-3">
        <Field id="fs-name-a" label={`${fs.name_a}’s name`}>
          <input id="fs-name-a" className="input" value={nameA} onChange={(e) => setNameA(e.target.value)} />
        </Field>
        <Field id="fs-name-b" label={`${fs.name_b}’s name`}>
          <input id="fs-name-b" className="input" value={nameB} onChange={(e) => setNameB(e.target.value)} />
        </Field>
        <Field id="fs-income-a" label={`${fs.name_a}’s net income per month`}>
          <input id="fs-income-a" className="input num" inputMode="decimal" placeholder="0,00 €" value={incomeA} onChange={(e) => setIncomeA(e.target.value)} />
        </Field>
        <Field id="fs-income-b" label={`${fs.name_b}’s net income per month`}>
          <input id="fs-income-b" className="input num" inputMode="decimal" placeholder="0,00 €" value={incomeB} onChange={(e) => setIncomeB(e.target.value)} />
        </Field>
        <p className="col-span-2 text-xs text-ink-muted">If you change a name, the money that person sends in is renamed too.</p>
        <button className="btn-primary col-span-2 justify-self-start" disabled={save.isPending}>Save names and incomes</button>
      </form>
      <ErrorNote error={save.error} />
    </Card>
  );
}

function SettleUpCard({ data }: { data: JointView }) {
  const today = useYears().data?.today ?? new Date().toISOString().slice(0, 10);
  const addShared = useAddShared();
  const delShared = useDeleteShared();
  const addSettlement = useAddSettlement();
  const delSettlement = useDeleteSettlement();
  const s = data.settle_up;
  const names: Record<Person, string> = { a: data.fair_share.name_a, b: data.fair_share.name_b };
  const [desc, setDesc] = useState('');
  const [amount, setAmount] = useState('');
  const [paidBy, setPaidBy] = useState<Person>('a');
  const [split, setSplit] = useState<'fair' | 'equal'>('fair');
  const parsed = parseAmount(amount);
  const valid = parsed !== null && parsed > 0;

  return (
    <Card className="col-span-7" title={<span className="flex items-center gap-1.5"><Handshake size={15} /> Settle up</span>}
      subtitle="Something for both of us that one of us paid from their own account. It does not change our pot.">
      <p className="mb-3 rounded-lg bg-bg px-3 py-2 text-sm" data-testid="settle-up">
        {s.owes ? <><b>{s.text}</b> <span className="num font-semibold">{fmtMoney(s.amount)}</span></> : <b>✓ {s.text}</b>}
        {s.owes && s.gets && (
          <button className="btn-secondary btn-sm ml-3" disabled={addSettlement.isPending}
            onClick={() => addSettlement.mutate({ date: today, from_person: s.owes!, amount: s.amount, note: 'Settled up' })}>
            Record that {names[s.owes]} paid it
          </button>
        )}
      </p>
      <ul className="max-h-48 divide-y divide-line/70 overflow-y-auto text-sm">
        {s.expenses.map((e) => (
          <li key={`e${e.id}`} className="group flex items-center gap-2 py-1.5">
            <span className="num w-16 text-xs text-ink-muted">{fmtDate(e.date, { short: true })}</span>
            <span className="flex-1 truncate">{e.desc || 'Shared cost'} <span className="text-xs text-ink-muted">· paid by {names[e.paid_by]} · {e.split === 'equal' ? 'half each' : 'fair share'}</span></span>
            <span className="num">{fmtMoney(e.amount)}</span>
            <button className="btn-ghost btn-sm opacity-0 group-hover:opacity-100" aria-label={`Delete shared cost ${e.desc}`} onClick={() => delShared.mutate(e.id)}><Trash2 size={12} /></button>
          </li>
        ))}
        {s.settlements.map((x) => (
          <li key={`s${x.id}`} className="group flex items-center gap-2 py-1.5 text-ink-soft">
            <span className="num w-16 text-xs text-ink-muted">{fmtDate(x.date, { short: true })}</span>
            <span className="flex-1 truncate">{names[x.from_person]} paid {names[x.from_person === 'a' ? 'b' : 'a']} {x.note && <span className="text-xs text-ink-muted">· {x.note}</span>}</span>
            <span className="num">{fmtMoney(x.amount)}</span>
            <button className="btn-ghost btn-sm opacity-0 group-hover:opacity-100" aria-label="Delete settlement" onClick={() => delSettlement.mutate(x.id)}><Trash2 size={12} /></button>
          </li>
        ))}
        {!s.expenses.length && !s.settlements.length && <li className="py-2 text-xs text-ink-muted">Nothing to settle yet.</li>}
      </ul>
      <form className="mt-3 flex items-center gap-2 border-t border-line pt-3" onSubmit={(e) => {
        e.preventDefault();
        if (valid) addShared.mutate({ date: today, desc: desc.trim(), amount: parsed!, paid_by: paidBy, split }, { onSuccess: () => { setDesc(''); setAmount(''); } });
      }}>
        <input className="input h-8" placeholder="What was it?" aria-label="Shared cost description" value={desc} onChange={(e) => setDesc(e.target.value)} />
        <input className="input h-8 w-24 num" inputMode="decimal" placeholder="€" aria-label="Shared cost amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <select className="input h-8 w-32" aria-label="Paid by" value={paidBy} onChange={(e) => setPaidBy(e.target.value as Person)}>
          <option value="a">{names.a} paid</option>
          <option value="b">{names.b} paid</option>
        </select>
        <select className="input h-8 w-28" aria-label="Split" value={split} onChange={(e) => setSplit(e.target.value as 'fair' | 'equal')}>
          <option value="fair">Fair share</option>
          <option value="equal">Half each</option>
        </select>
        <button className="btn-primary" disabled={!valid || addShared.isPending}>Add</button>
      </form>
      <ErrorNote error={addShared.error || delShared.error || addSettlement.error || delSettlement.error} />
    </Card>
  );
}
