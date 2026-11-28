import { useState } from 'react';
import { saveFile } from '../../api/client';
import { fetchTaxFile, useSaveTaxSettings, useTax } from '../../api/queries';
import { Hint } from '../../components/ui/Card';
import { ErrorNote, Loading } from '../../components/ui/Feedback';
import { Modal } from '../../components/ui/Modal';
import { fmtMoney } from '../../lib/format';

/**
 * The yearly tax export: what is in tax-relevant categories, the commute
 * estimate, and a CSV for the Lohnsteuerhilfeverein. Totals come from the
 * backend (services/tax_export.py).
 */
export function TaxExportModal({ year, open, onClose }: { year: number; open: boolean; onClose: () => void }) {
  const { data, isLoading, error } = useTax(year);
  const save = useSaveTaxSettings(year);
  const [days, setDays] = useState<string | null>(null);
  const [km, setKm] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [fileError, setFileError] = useState<unknown>(null);
  const daysValue = days ?? (data?.commute_days != null ? String(data.commute_days) : '');
  const kmValue = km ?? (data?.commute_km != null ? String(data.commute_km) : '');

  const saveCommute = () => {
    save.mutate({
      commute_days: daysValue.trim() ? Number(daysValue) : null,
      commute_km: kmValue.trim() ? Number(kmValue.replace(',', '.')) : null,
    });
  };

  const exportCsv = async () => {
    setStatus(null);
    setFileError(null);
    try {
      const result = await saveFile(await fetchTaxFile(year));
      setStatus(result.saved ? `Saved as ${result.name}` : result.error ?? null);
    } catch (e) {
      setFileError(e);
    }
  };

  return (
    <Modal title={`Tax export ${year}`} open={open} onClose={onClose} width="lg"
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Close</button>
        <button className="btn-primary" onClick={exportCsv} disabled={!data}>Save as CSV…</button>
      </>}>
      {isLoading ? <Loading /> : error || !data ? <ErrorNote error={error} /> : (
        <div className="space-y-4 text-sm">
          <Hint>
            Everything in categories marked § (tax-relevant) in {year}, plus the commute estimate — a list to take to your
            Lohnsteuerhilfeverein. It is an estimate, not tax advice.
          </Hint>
          {!data.categories.length ? (
            <p className="rounded-md bg-warning-tint px-3 py-2 text-xs text-warning">
              No category is marked tax-relevant yet. Tick § next to e.g. tuition or work equipment in Categories.
            </p>
          ) : (
            <table className="w-full text-sm" data-testid="tax-totals">
              <thead className="text-left text-xs text-ink-muted">
                <tr className="border-b border-line"><th className="py-1.5">Category</th><th className="py-1.5 text-right">Transactions</th><th className="py-1.5 text-right">Amount</th></tr>
              </thead>
              <tbody className="num divide-y divide-line/60">
                {data.totals.map((t) => (
                  <tr key={`${t.type}-${t.cat}`}>
                    <td className="py-1.5">{t.cat}{t.type === 'income' && <span className="ml-1 text-xs text-ink-muted">(income)</span>}</td>
                    <td className="py-1.5 text-right">{t.count}</td>
                    <td className="py-1.5 text-right">{fmtMoney(t.amount)}</td>
                  </tr>
                ))}
                {data.commute && (
                  <tr>
                    <td className="py-1.5">Commute: {data.commute.days} days × {data.commute.km} km × {fmtMoney(data.commute.rate)}</td>
                    <td />
                    <td className="py-1.5 text-right">{fmtMoney(data.commute.amount)}</td>
                  </tr>
                )}
              </tbody>
              <tfoot className="num">
                <tr className="border-t border-line font-medium"><td className="py-1.5">Work-related costs</td><td /><td className="py-1.5 text-right">{fmtMoney(data.work_costs_total)}</td></tr>
              </tfoot>
            </table>
          )}
          <div className="flex items-end gap-2 border-t border-line pt-3">
            <div>
              <label className="label" htmlFor="tax-days">Office days in {year}</label>
              <input id="tax-days" type="number" min={0} max={366} className="input h-8 w-32 num" value={daysValue} onChange={(e) => setDays(e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="tax-km">Km one way</label>
              <input id="tax-km" inputMode="decimal" className="input h-8 w-28 num" value={kmValue} onChange={(e) => setKm(e.target.value)} />
            </div>
            <button className="btn-secondary h-8" onClick={saveCommute} disabled={save.isPending}>Save commute</button>
          </div>
          {status && <p role="status" className="text-xs text-positive">✓ {status}</p>}
          <ErrorNote error={save.error || fileError} />
        </div>
      )}
    </Modal>
  );
}
