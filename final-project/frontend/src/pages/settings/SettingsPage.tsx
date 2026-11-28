import { CircleAlert } from 'lucide-react';
import { useState } from 'react';
import { openFile, saveFile, type OpenedFile } from '../../api/client';
import { fetchDataJson, fetchTransactionsCsv, useMakeBackup, useRestoreBackup, useVerifyBackup } from '../../api/queries';
import { Card } from '../../components/ui/Card';
import { ConfirmButton } from '../../components/ui/ConfirmButton';
import { ErrorNote } from '../../components/ui/Feedback';
import { Field } from '../../components/ui/Field';
import { StatusBadge, StatusText } from '../../components/ui/StatusBadge';
import type { BackupCheck } from '../../lib/types';
import { AppearanceCard } from './AppearanceCard';
import { CalendarSettingsCard } from './CalendarSettingsCard';

const MIN_PASSWORD = 10;

/** Where the app keeps its files when no test folder is set (backend config.data_dir()). */
const DATA_FOLDER = '~/Library/Application Support/Personal Centwise/';

/**
 * Settings: appearance, data safety (encrypted backups: make, verify, restore;
 * the plain export), Apple Calendar and the keyboard shortcuts. All encryption,
 * checking and file contents are done by the backend (services/backup.py);
 * this page only passes files to and from the Save/Open windows.
 */
export function SettingsPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-page-title text-ink">Settings</h1>
        <p className="mt-0.5 text-[13px] text-ink-soft">Your data stays on this Mac. Nothing here is sent anywhere.</p>
      </div>
      <DataSafeBar />
      <div className="grid grid-cols-2 items-start gap-4">
        <div className="space-y-4">
          <AppearanceCard />
          <MakeBackupCard />
          <ExportCard />
        </div>
        <div className="space-y-4">
          <VerifyCard />
          <CalendarSettingsCard />
          <ShortcutsCard />
        </div>
      </div>
    </div>
  );
}

function DataSafeBar() {
  return (
    <section className="flex items-center gap-4 rounded-card border border-line bg-surface px-4 py-3 shadow-card" data-testid="data-safe">
      <StatusBadge kind="positive">Data safe</StatusBadge>
      <p className="flex-1 text-body text-ink">
        <b className="font-semibold">Up to 20 automatic backups kept on this Mac.</b>{' '}
        <span className="text-ink-soft">For extra safety, make an encrypted backup to a USB stick once a month.</span>
      </p>
      <span className="shrink-0 font-mono text-label text-ink-soft" title="Data folder">{DATA_FOLDER}</span>
    </section>
  );
}

function MakeBackupCard() {
  const make = useMakeBackup();
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [fileError, setFileError] = useState<unknown>(null);
  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;
  const mismatch = repeat.length > 0 && repeat !== password;
  const valid = password.length >= MIN_PASSWORD && password === repeat;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setStatus(null);
    setFileError(null);
    const file = await make.mutateAsync(password).catch(() => null);
    if (!file) return;
    try {
      const result = await saveFile(file);
      if (result.saved) {
        setStatus(`Saved as ${result.name}. Keep the password somewhere safe — without it the backup cannot be opened.`);
        setPassword('');
        setRepeat('');
      } else if (result.error) {
        setFileError(new Error(result.error));
      }
    } catch (err) {
      setFileError(err);
    }
  };

  return (
    <Card title="Make an encrypted backup">
      <form onSubmit={submit} className="space-y-3">
        <Field id="backup-password" label={`Password (at least ${MIN_PASSWORD} characters)`}>
          <input id="backup-password" type="password" autoComplete="new-password" className="input" value={password}
            onChange={(e) => setPassword(e.target.value)} aria-invalid={tooShort} />
        </Field>
        <Field id="backup-repeat" label="The same password again" error={mismatch ? 'The two passwords are not the same.' : undefined}>
          <input id="backup-repeat" type="password" autoComplete="new-password" className={`input ${mismatch ? 'input-error' : ''}`} value={repeat}
            onChange={(e) => setRepeat(e.target.value)} aria-invalid={mismatch} aria-describedby={mismatch ? 'backup-repeat-error' : undefined} />
        </Field>
        <p className="flex items-start gap-2.5 rounded-lg bg-warning-tint px-3 py-2.5 text-[13px] leading-[18px] text-warning-ink">
          <CircleAlert size={16} className="mt-px shrink-0" aria-hidden />
          <span><b className="font-semibold">The password is not stored anywhere.</b> If you forget it, nobody can open the backup — not even this app.</span>
        </p>
        <button className="btn-primary" disabled={!valid || make.isPending}>{make.isPending ? 'Encrypting…' : 'Make backup and save…'}</button>
        {status && <p role="status"><StatusText kind="positive">{status}</StatusText></p>}
        <ErrorNote error={make.error || fileError} />
      </form>
    </Card>
  );
}

function VerifyCard() {
  const verify = useVerifyBackup();
  const restore = useRestoreBackup();
  const [file, setFile] = useState<OpenedFile | null>(null);
  const [password, setPassword] = useState('');
  const [result, setResult] = useState<BackupCheck | null>(null);
  const [pickError, setPickError] = useState<unknown>(null);

  const pick = async () => {
    setPickError(null);
    setResult(null);
    restore.reset();
    try {
      const opened = await openFile(['pcbackup']);
      if (opened?.error) setPickError(new Error(opened.error));
      else if (opened) setFile(opened);
    } catch (err) {
      setPickError(err);
    }
  };

  const check = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !password) return;
    verify.mutate({ password, content_base64: file.content_base64 }, { onSuccess: setResult });
  };

  const profiles = result?.summary.map((s) => s.label).join(' and ') ?? '';

  return (
    <Card title="Verify or restore a backup">
      <div className="space-y-3">
        <div className="flex items-center gap-2.5">
          <button type="button" className="btn-secondary shrink-0" onClick={pick}>Choose backup file…</button>
          <span className="truncate text-label text-ink-soft" data-testid="backup-file">{file ? file.name : 'No file chosen'}</span>
        </div>
        <form className="flex items-end gap-2" onSubmit={check}>
          <Field id="verify-password" label="Its password" className="flex-1">
            <input id="verify-password" type="password" autoComplete="off" className="input" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <button className="btn-primary" disabled={!file || !password || verify.isPending}>
            {verify.isPending ? 'Checking…' : 'Verify backup'}
          </button>
        </form>
        <ErrorNote error={pickError || verify.error} />

        {result && (
          <div className="space-y-2 rounded-lg border border-line bg-bg p-3" data-testid="verify-result">
            {result.ok
              ? <StatusBadge kind="positive">All totals match</StatusBadge>
              : <StatusBadge kind="negative">The backup did not pass the check</StatusBadge>}
            <ul className="num list-disc space-y-0.5 pl-5 text-[13px] leading-5 text-ink-soft">
              {result.summary.map((s) => (
                <li key={s.profile}>{s.label}: {s.transactions} transactions, years {s.years.join(', ') || '—'}, {s.goals} goals</li>
              ))}
              {result.problems.map((p) => <li key={p} className="text-negative">{p}</li>)}
              {result.created && <li className="text-ink-muted">Made on {result.created.replace('T', ' at ')}</li>}
            </ul>
            {result.ok && !restore.isSuccess && (
              <ConfirmButton
                label="Restore this backup…"
                question={`Replace the data of ${profiles} with this backup? Your current files are first kept as a safety copy next to them.`}
                confirmLabel={restore.isPending ? 'Restoring…' : 'Yes, restore'}
                keepLabel="Keep my current data"
                busy={restore.isPending}
                onConfirm={() => file && restore.mutate({ password, content_base64: file.content_base64 })}
              />
            )}
          </div>
        )}
        {restore.isSuccess && (
          <p role="status"><StatusText kind="positive">Restored. Safety copies: {restore.data.safety_copies?.join(', ') || 'none needed'}.</StatusText></p>
        )}
        <ErrorNote error={restore.error} />
      </div>
    </Card>
  );
}

function ExportCard() {
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const run = async (fetcher: () => Promise<{ filename: string; content_base64: string }>) => {
    setStatus(null);
    setError(null);
    try {
      const result = await saveFile(await fetcher());
      if (result.saved) setStatus(`Saved as ${result.name}`);
    } catch (err) {
      setError(err);
    }
  };
  return (
    <Card title="Export everything">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn-secondary" onClick={() => run(fetchTransactionsCsv)}>All transactions (CSV)…</button>
          <button type="button" className="btn-secondary" onClick={() => run(fetchDataJson)}>The whole data file (JSON)…</button>
        </div>
        <StatusText kind="warning">These two files are not encrypted. Keep them somewhere private.</StatusText>
        {status && <p role="status"><StatusText kind="positive">{status}</StatusText></p>}
        <ErrorNote error={error} />
      </div>
    </Card>
  );
}

/** What the header listens for (components/Header.tsx) plus the page shortcuts. */
const SHORTCUTS: [string, string][] = [
  ['Overview … Settings', '⌘1–6'],
  ['Add transaction', '⌘N'],
  ['Calculator', '⌘K'],
  ['Search transactions', '⌘F'],
  ['Save quick entry rows', '⌘↵'],
  ['Close a window or question', 'Esc'],
];

function ShortcutsCard() {
  return (
    <Card title="Keyboard shortcuts">
      <dl className="grid grid-cols-2 gap-x-6" data-testid="shortcuts">
        {SHORTCUTS.map(([what, keys]) => (
          <div key={what} className="flex h-8 items-center justify-between gap-2 border-b border-line text-[13px]">
            <dt className="text-ink-soft">{what}</dt>
            <dd><kbd className="rounded-input border border-line-strong bg-bg px-1.5 font-sans text-label leading-5 text-ink">{keys}</kbd></dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
