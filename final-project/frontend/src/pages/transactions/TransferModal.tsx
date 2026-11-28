import { useState } from 'react';
import { useTransferToJoint } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { Modal } from '../../components/ui/Modal';
import { parseAmount } from '../../lib/format';
import { defaultDate } from './TransactionForm';

/** Personal → Joint: the backend saves an expense here and the matching income in Joint, linked. */
export function TransferModal({ year, open, onClose }: { year: number; open: boolean; onClose: () => void }) {
  const transfer = useTransferToJoint();
  const [date, setDate] = useState(defaultDate(year));
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const parsed = parseAmount(amount);
  const valid = parsed !== null && parsed > 0 && date;
  const close = () => { transfer.reset(); onClose(); };
  return (
    <Modal title="Transfer to Joint" open={open} onClose={close}>
      <form className="space-y-3 text-sm" onSubmit={(e) => {
        e.preventDefault();
        if (valid) transfer.mutate({ date, amount: parsed!, note: note.trim() }, { onSuccess: () => { setAmount(''); setNote(''); close(); } });
      }}>
        <p className="text-xs text-ink-muted">
          Saves two linked records: an expense “Transfer to Joint” here, and the matching income “From …” under your name
          in the Joint profile. Editing or deleting one changes the other. The two profiles stay separate otherwise.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="transfer-amount">Amount (€)</label>
            <input id="transfer-amount" inputMode="decimal" className="input num" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
          </div>
          <div>
            <label className="label" htmlFor="transfer-date">Date</label>
            <input id="transfer-date" type="date" className="input num" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="transfer-note">Note <span className="font-normal text-ink-muted">(optional)</span></label>
          <input id="transfer-note" className="input" placeholder="e.g. November share" value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        <ErrorNote error={transfer.error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={close}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={!valid || transfer.isPending}>Transfer</button>
        </div>
      </form>
    </Modal>
  );
}
