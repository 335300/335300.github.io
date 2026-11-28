import { FileUp } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { useCategories, useImportCommit, useImportPreview } from '../../api/queries';
import { ErrorNote } from '../../components/ui/Feedback';
import { Modal } from '../../components/ui/Modal';
import { fmtDate, fmtExpense, fmtMoney } from '../../lib/format';
import type { ImportPreview, ImportPreviewRow, ImportReason } from '../../lib/types';

const REASON: Record<ImportReason, string> = {
  pending: 'Still pending at the bank',
  currency: 'Not in euros',
  zero: 'Zero amount',
  not_tracked: 'Month not tracked in the app',
  bank_ref: 'Already saved (same bank reference)',
  same_amount_date_payee: 'Already saved (same amount, date and payee)',
  same_amount_date: 'Possibly saved by hand (same amount and date)',
};

/** Rows that can never be saved (the backend would refuse them or they are not final). */
const LOCKED: ImportReason[] = ['pending', 'currency', 'zero', 'not_tracked'];

/** Read a file as base64 so it can cross the bridge to the backend unchanged (its encoding included). */
async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

interface Choice {
  include: boolean;
  cat: string;
}

/**
 * Import a Sparkasse CSV-CAMT statement. The backend reads the file, checks for
 * duplicates and applies payee rules; this window only shows the result and lets
 * you untick rows or change a category before saving.
 */
export function ImportModal({ year, open, onClose }: { year: number; open: boolean; onClose: () => void }) {
  const preview = useImportPreview();
  const commit = useImportCommit();
  const categories = useCategories(year);
  const fileRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<ImportPreview | null>(null);
  const [choices, setChoices] = useState<Record<number, Choice>>({});
  const [saved, setSaved] = useState<{ created: number; skipped: number } | null>(null);

  const reset = () => {
    setResult(null);
    setChoices({});
    setSaved(null);
    preview.reset();
    commit.reset();
    if (fileRef.current) fileRef.current.value = '';
  };
  const close = () => { reset(); onClose(); };

  const pick = async (file: File | undefined) => {
    if (!file) return;
    setSaved(null);
    commit.reset();
    const data = await preview.mutateAsync({ filename: file.name, content_base64: await toBase64(file) }).catch(() => null);
    if (!data) return;
    setResult(data);
    setChoices(Object.fromEntries(data.rows.map((r) => [r.line, { include: r.status === 'new', cat: r.cat }])));
  };

  const chosen = useMemo(
    () => (result?.rows ?? []).filter((r) => choices[r.line]?.include),
    [result, choices],
  );

  const save = () => {
    commit.mutate(
      chosen.map((r) => ({
        date: r.date, type: r.type, amount: r.amount, cat: choices[r.line].cat.trim() || r.cat,
        desc: r.desc, payee: r.payee, bank_ref: r.bank_ref,
      })),
      { onSuccess: (res) => { setSaved(res); setResult(null); } },
    );
  };

  const names = (kind: 'expense' | 'income') => (categories.data?.[kind] ?? []).map((c) => c.name);

  return (
    <Modal title="Import a statement file" open={open} onClose={close} width="xl"
      footer={result ? (
        <>
          <button className="btn-secondary" onClick={reset}>Choose another file</button>
          <button className="btn-primary" onClick={save} disabled={!chosen.length || commit.isPending}>
            Save {chosen.length} row{chosen.length === 1 ? '' : 's'}
          </button>
        </>
      ) : (
        <button className="btn-secondary" onClick={close}>Close</button>
      )}
    >
      {!result && (
        <div className="space-y-3 text-sm">
          {saved && (
            <p role="status" className="rounded-md bg-positive-tint px-3 py-2 text-positive">
              Saved {saved.created} transaction{saved.created === 1 ? '' : 's'}
              {saved.skipped ? ` · ${saved.skipped} were already saved` : ''}.
            </p>
          )}
          <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-line px-4 py-8 text-center hover:bg-bg">
            <FileUp size={22} className="text-ink-muted" />
            <span className="font-medium text-ink-soft">Choose a Sparkasse CSV-CAMT file</span>
            <span className="text-xs text-ink-muted">Nothing is saved until you check the preview and press Save.</span>
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="sr-only" aria-label="Statement file"
              onChange={(e) => pick(e.target.files?.[0])} />
          </label>
          {preview.isPending && <p className="text-xs text-ink-muted">Reading the file…</p>}
          <ErrorNote error={preview.error} />
          <p className="text-xs text-ink-muted">
            How to get the file: in Sparkasse online banking open your account's <b>Umsätze</b>, choose the period, then
            <b> Export</b> → <b>CSV-CAMT V8</b>. Rows that match a payee rule get their category automatically.
          </p>
        </div>
      )}

      {result && (
        <div className="space-y-3">
          <p className="text-sm" data-testid="import-summary">
            <b className="text-positive">{result.new} new</b>, <b>{result.skipped} skipped</b> of {result.total} rows in {result.filename}.
            {Object.keys(result.skipped_by_reason).length > 0 && (
              <span className="text-xs text-ink-muted"> Skipped: {Object.entries(result.skipped_by_reason)
                .map(([reason, n]) => `${n} × ${REASON[reason as ImportReason].toLowerCase()}`).join(' · ')}.</span>
            )}
          </p>
          <p className="text-xs text-ink-muted">Untick a row to leave it out, or tick a skipped duplicate if it really is new. You can change any category.</p>
          <div className="max-h-[55vh] overflow-y-auto rounded-lg border border-line">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface text-left text-xs text-ink-muted">
                <tr className="border-b border-line">
                  <th className="w-8 px-2 py-1.5"><span className="sr-only">Save</span></th>
                  <th className="px-2 py-1.5">Date</th>
                  <th className="px-2 py-1.5">Payee and purpose</th>
                  <th className="px-2 py-1.5 text-right">Amount</th>
                  <th className="px-2 py-1.5">Category</th>
                  <th className="px-2 py-1.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/70">
                {result.rows.map((r) => (
                  <PreviewRow key={r.line} row={r} choice={choices[r.line]} options={names(r.type)}
                    onChange={(c) => setChoices((all) => ({ ...all, [r.line]: { ...all[r.line], ...c } }))} />
                ))}
              </tbody>
            </table>
          </div>
          <datalist id="import-cats-expense">{names('expense').map((n) => <option key={n} value={n} />)}</datalist>
          <datalist id="import-cats-income">{names('income').map((n) => <option key={n} value={n} />)}</datalist>
          <ErrorNote error={commit.error} />
        </div>
      )}
    </Modal>
  );
}

function PreviewRow({ row, choice, options, onChange }: {
  row: ImportPreviewRow;
  choice: Choice | undefined;
  options: string[];
  onChange: (c: Partial<Choice>) => void;
}) {
  const locked = row.reason !== null && LOCKED.includes(row.reason);
  const include = choice?.include ?? false;
  const moved = row.date !== row.bank_date;
  const statusWord = row.status === 'new' ? 'New' : row.status === 'duplicate' ? 'Duplicate'
    : row.status === 'possible_duplicate' ? 'Possible duplicate' : 'Skipped';
  const statusCls = row.status === 'new' ? 'bg-positive-tint text-positive'
    : row.status === 'possible_duplicate' ? 'bg-warning-tint text-warning' : 'bg-neutral-tint text-ink-soft';
  return (
    <tr className={include ? '' : 'text-ink-muted'}>
      <td className="px-2 py-1.5">
        <input type="checkbox" checked={include} disabled={locked} aria-label={`Save row ${row.line}`}
          onChange={(e) => onChange({ include: e.target.checked })} />
      </td>
      <td className="num whitespace-nowrap px-2 py-1.5">
        {fmtDate(row.date, { short: true })}
        {moved && <span className="block text-xs text-ink-muted">paid {fmtDate(row.bank_date, { short: true })}</span>}
      </td>
      <td className="max-w-[22rem] px-2 py-1.5">
        <span className="block truncate">{row.payee || '—'}</span>
        {row.purpose && <span className="block truncate text-xs text-ink-muted">{row.purpose}</span>}
      </td>
      <td className={`num whitespace-nowrap px-2 py-1.5 text-right ${row.type === 'income' ? 'text-positive' : ''}`}>
        {row.type === 'income' ? `+${fmtMoney(row.amount)}` : fmtExpense(row.amount)}
      </td>
      <td className="px-2 py-1.5">
        <input className="input h-7 w-40 text-xs" value={choice?.cat ?? row.cat} disabled={locked}
          list={`import-cats-${row.type}`} aria-label={`Category for row ${row.line}`}
          title={options.includes(choice?.cat ?? row.cat) ? undefined : 'A new category will be created'}
          onChange={(e) => onChange({ cat: e.target.value })} />
      </td>
      <td className="px-2 py-1.5">
        <span className={`inline-flex whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${statusCls}`}>{statusWord}</span>
        {row.reason && <span className="block text-xs text-ink-muted">{REASON[row.reason]}</span>}
        {row.match && (
          <span className="num block truncate text-xs text-ink-muted" title={row.match.desc}>
            Saved: {fmtDate(row.match.date, { short: true })} · {row.match.cat}
          </span>
        )}
      </td>
    </tr>
  );
}
