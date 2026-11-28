import { useDeferredValue, useMemo, useState } from 'react';
import { useApplyDistribution, useDistributionPreview } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { Modal } from '../../components/ui/Modal';
import { GoalBadge } from '../../components/ui/StatusBadge';
import { fmtMoney, parseAmount } from '../../lib/format';
import type { Distribution } from '../../lib/types';

/**
 * Give this month's unassigned savings a job: an amount per goal, saved as one
 * contribution each. The running "left after this" figure comes from the
 * backend's preview — nothing is added up here.
 */
export function DistributeModal({ year, data, onClose }: { year: number; data: Distribution; onClose: () => void }) {
  const suggested = () => Object.fromEntries(data.suggested.map((s) => [s.goal_id, s.suggested ? String(s.suggested) : '']));
  const [values, setValues] = useState<Record<number, string>>(suggested);
  const apply = useApplyDistribution(year);

  const parsed = data.suggested.map((s) => ({ goal_id: s.goal_id, amount: values[s.goal_id]?.trim() ? parseAmount(values[s.goal_id]) : 0 }));
  const invalid = parsed.some((p) => p.amount === null || p.amount < 0);
  const body = useMemo(
    () => ({ month: data.month, allocations: parsed.filter((p) => p.amount !== null && p.amount > 0).map((p) => ({ goal_id: p.goal_id, amount: p.amount! })) }),
    [data.month, JSON.stringify(parsed)]
  );
  const deferred = useDeferredValue(body);
  const preview = useDistributionPreview(year, deferred, !invalid);
  const p = preview.data;
  const nothing = body.allocations.length === 0;

  return (
    <Modal
      title={`Distribute ${data.month_name}’s savings`}
      open
      onClose={onClose}
      width="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={invalid || nothing || apply.isPending}
            onClick={() => apply.mutate(body, { onSuccess: onClose })}>
            Put toward goals
          </button>
        </>
      }
    >
      <div className="num grid grid-cols-3 gap-4 rounded-lg bg-bg px-4 py-3 text-sm">
        <Figure label={`Kept in ${data.month_name}`} value={fmtMoney(data.saved)} />
        <Figure label="Already with goals" value={fmtMoney(data.to_goals)} />
        <Figure label="Left to assign" value={fmtMoney(data.left_to_assign)} strong />
      </div>

      <table className="mt-4 w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-ink-muted">
            <th className="pb-2 font-medium">Goal</th>
            <th className="pb-2 text-right font-medium">Still missing</th>
            <th className="pb-2 text-right font-medium">Needs per month</th>
            <th className="w-36 pb-2 pl-4 text-right font-medium">Add now (€)</th>
          </tr>
        </thead>
        <tbody>
          {data.suggested.map((s) => {
            const mine = parsed.find((x) => x.goal_id === s.goal_id)?.amount;
            const bad = mine === null || (mine ?? 0) < 0;
            return (
              <tr key={s.goal_id} className="border-b border-line/70 last:border-0">
                <td className="py-2.5">
                  <div className="font-medium">{s.name}</div>
                  <div className="mt-0.5"><GoalBadge status={s.status} /></div>
                </td>
                <td className="num py-2.5 text-right text-ink-soft">{fmtMoney(s.remaining)}</td>
                <td className="num py-2.5 text-right text-ink-soft">{s.required_monthly_pace === null ? 'Deadline passed' : fmtMoney(s.required_monthly_pace)}</td>
                <td className="py-2.5 pl-4">
                  <input className={`input num h-8 text-right ${bad ? 'border-negative' : ''}`} inputMode="decimal" placeholder="0"
                    aria-label={`Amount for ${s.name}`} value={values[s.goal_id] ?? ''}
                    onChange={(e) => setValues((v) => ({ ...v, [s.goal_id]: e.target.value }))} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="mt-3 flex items-center gap-2 text-xs">
        <button className="btn-ghost btn-sm" onClick={() => setValues(suggested())}>Use the suggestion</button>
        <button className="btn-ghost btn-sm" onClick={() => setValues({})}>Clear</button>
        <span className="flex-1" />
        {p && !invalid && (
          <span className="num text-sm" role="status">
            Adding <strong>{fmtMoney(p.adding)}</strong> · left after this{' '}
            <strong className={p.over ? 'text-warning' : 'text-secondary'}>{fmtMoney(p.left_after)}</strong>
          </span>
        )}
      </div>
      {p?.over && !invalid && (
        <p className="mt-2 rounded-md bg-warning-tint px-3 py-2 text-xs text-warning">
          ⚠ This is more than {data.month_name} kept. You can still do it — the difference comes from the balance you already had.
        </p>
      )}
      {invalid && <p className="mt-2 text-xs text-negative">Enter amounts like 150 or 150.50 — or leave a goal empty.</p>}
      <p className="mt-3 text-xs leading-relaxed text-ink-muted">
        The suggestion gives each goal its monthly pace, nearest deadline first, until the money runs out. Goal money stays in
        your account — it is only earmarked, so your balance does not change; your liquidity goes down by what you assign.
      </p>
      <ErrorNote error={apply.error || preview.error} />
    </Modal>
  );
}

function Figure({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <div className="text-xs text-ink-muted">{label}</div>
      <div className={`mt-0.5 ${strong ? 'text-base font-semibold text-secondary' : 'font-medium'}`}>{value}</div>
    </div>
  );
}
