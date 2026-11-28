import { useState } from 'react';
import { useUpdateYear } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { Modal } from '../../components/ui/Modal';
import { fmtMoney, MONTHS, parseAmount } from '../../lib/format';
import type { YearSummary } from '../../lib/types';

/**
 * The year's opening balance and first tracked month, as one short line
 * ("tracking starts January 2026 with 1.000,00 € · Change"). "Change" opens a
 * small dialog. Set on first run; editable here.
 */
export function StartingPoint({ year, joint = false }: { year: YearSummary; joint?: boolean }) {
  const [editing, setEditing] = useState(false);
  const month = `${MONTHS[year.start_month + 1] ?? 'January'} ${year.year}`;
  return (
    <span data-testid="starting-point">
      {joint ? 'We started tracking in ' : 'tracking starts '}
      <span className="text-ink">{month}</span> with <span className="num text-ink">{fmtMoney(year.opening_balance)}</span>{' '}
      <button type="button" className="font-medium text-primary hover:underline" onClick={() => setEditing(true)}>Change</button>
      {editing && <StartingPointModal key={`${year.opening_balance}-${year.start_month}`} year={year} onClose={() => setEditing(false)} />}
    </span>
  );
}

function StartingPointModal({ year, onClose }: { year: YearSummary; onClose: () => void }) {
  const update = useUpdateYear(year.year);
  const [balance, setBalance] = useState(String(year.opening_balance));
  const [first, setFirst] = useState(year.start_month + 1);
  const parsed = parseAmount(balance);
  return (
    <Modal title="Starting point" open onClose={onClose}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (parsed === null) return;
          update.mutate({ opening_balance: parsed, start_month: first - 1 }, { onSuccess: onClose });
        }}
      >
        <div>
          <label className="label" htmlFor="sp-month">Tracking starts in</label>
          <select id="sp-month" className="input" value={first} onChange={(e) => setFirst(Number(e.target.value))}>
            {MONTHS.map((m, i) => <option key={m} value={i}>{m} {year.year}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="sp-balance">Money at the start of that month (€)</label>
          <input id="sp-balance" inputMode="decimal" className="input num" value={balance} onChange={(e) => setBalance(e.target.value)} />
        </div>
        <ErrorNote error={update.error} />
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={parsed === null || update.isPending}>Save</button>
        </div>
      </form>
    </Modal>
  );
}
