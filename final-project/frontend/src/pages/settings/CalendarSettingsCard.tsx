import { Smartphone } from 'lucide-react';
import { useAllowCalendar, useCalendarStatus, usePrefs, useRemoveOwnCalendars, useSyncCalendar, useUpdatePrefs } from '../../api/queries';
import { Card } from '../../components/ui/Card';
import { ConfirmButton } from '../../components/ui/ConfirmButton';
import { ErrorNote } from '../../components/ui/Feedback';
import { StatusText } from '../../components/ui/StatusBadge';
import { fmtDate } from '../../lib/format';
import type { CalendarStatus } from '../../lib/types';

/**
 * Settings → Calendar: Apple Calendar access and which calendars the Calendar
 * tab shows. One choice for Personal and Joint (app-state.json, not data.json).
 */
export function CalendarSettingsCard() {
  const status = useCalendarStatus();
  const allow = useAllowCalendar();
  const prefs = usePrefs();
  const update = useUpdatePrefs();
  const hidden = prefs.data?.calendar_hidden ?? [];
  const access = status.data?.access;

  const setShown = (id: string, shown: boolean) =>
    update.mutate({ calendar_hidden: shown ? hidden.filter((h) => h !== id) : [...hidden, id] });

  return (
    <Card title="Apple Calendar" testId="calendar-card">
      <div className="space-y-3 text-[13px]" data-testid="calendar-settings">
        {access === 'full' && <StatusText kind="positive">Apple Calendar allowed</StatusText>}
        {access === 'not_asked' && (
          <div className="flex items-center gap-3">
            <StatusText kind="neutral" className="flex-1">Apple Calendar not allowed yet</StatusText>
            {allow.isPending
              ? <span className="text-label text-ink-soft">Waiting for your answer in the macOS window…</span>
              : <button type="button" className="btn-primary" onClick={() => allow.mutate(undefined)}>Allow calendar access</button>}
          </div>
        )}
        {(access === 'denied' || access === 'restricted' || access === 'write_only') && (
          <StatusText kind="warning">
            Calendar access is off. Turn it on in System Settings → Privacy &amp; Security → Calendars → Personal Centwise (Full Access).
          </StatusText>
        )}
        {(access === 'unavailable' || access === 'unknown') && (
          <StatusText kind="neutral">Apple Calendar cannot be read on this Mac.</StatusText>
        )}

        {access === 'full' && (
          <fieldset>
            <legend className="label">Calendars to show — the same in Personal and Joint</legend>
            {!status.data?.calendars.length ? <p className="text-ink-muted">No calendars found.</p> : (
              <ul className="space-y-1">
                {status.data.calendars.map((c) => {
                  const id = `cal-${c.id}`;
                  return (
                    <li key={c.id} className="flex h-8 items-center gap-2.5">
                      <input id={id} type="checkbox" className="h-4 w-4 accent-primary" checked={!hidden.includes(c.id)} onChange={(e) => setShown(c.id, e.target.checked)} />
                      {/* The calendar's own colour, set in Apple Calendar (not an app colour). */}
                      <span className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ backgroundColor: c.color }} aria-hidden />
                      <label htmlFor={id} className="flex-1 truncate">{c.title}</label>
                      <span className="truncate text-label text-ink-muted">{c.account}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </fieldset>
        )}
        {access === 'full' && status.data && <IphoneSync status={status.data} />}
        {status.data?.source === 'fake' && <p className="text-label text-ink-muted">Test calendar with made-up events.</p>}
        <ErrorNote error={status.error || allow.error || update.error} />
      </div>
    </Card>
  );
}

/** "2026-11-18T15:40" → "18 Nov, 15:40". */
const whenSynced = (iso: string) => `${fmtDate(iso.slice(0, 10), { short: true })}, ${iso.slice(11, 16)}`;

/**
 * Money dates on the iPhone: on/off, last sync, "Sync now", and removing the app's own
 * iCloud calendars. The changes themselves are worked out by the backend.
 */
function IphoneSync({ status }: { status: CalendarStatus }) {
  const prefs = usePrefs();
  const update = useUpdatePrefs();
  const sync = useSyncCalendar();
  const remove = useRemoveOwnCalendars();
  const on = prefs.data?.calendar_push ?? false;
  const made = Object.keys(prefs.data?.calendar_own_ids ?? {}).length > 0;
  const [personal, joint] = status.own_calendars;

  return (
    <fieldset className="space-y-2 border-t border-line pt-3" data-testid="iphone-sync">
      <legend className="label flex items-center gap-1.5"><Smartphone size={13} /> Money dates on your iPhone</legend>
      <div className="flex items-center gap-2">
        <input id="cal-push" type="checkbox" className="h-4 w-4 accent-primary" checked={on} onChange={(e) => update.mutate({ calendar_push: e.target.checked })} />
        <label htmlFor="cal-push">Send them to “{personal}” and “{joint}” in iCloud</label>
      </div>
      <p className="text-label text-ink-muted">Bill and goal names, never amounts · the next 6 months · reminders follow your calendar’s default alert for all-day events.</p>
      {on && (
        <div className="flex items-center gap-2 text-label">
          <span className="flex-1 text-ink-soft" data-testid="last-sync">
            {status.last_sync ? `Last synced ${whenSynced(status.last_sync)}` : 'Not synced yet'}
          </span>
          <button type="button" className="btn-secondary btn-sm" onClick={() => sync.mutate()} disabled={sync.isPending}>
            {sync.isPending ? 'Syncing…' : 'Sync now'}
          </button>
        </div>
      )}
      {sync.data && sync.data.added !== undefined && (
        <p role="status"><StatusText kind="positive">{sync.data.added} added, {sync.data.updated} changed, {sync.data.removed} removed</StatusText></p>
      )}
      {made && (
        <div className="border-t border-line pt-3">
          <ConfirmButton
            compact
            label="Remove the Centwise calendars…"
            question={`Delete “${personal}” and “${joint}” from iCloud — also from your iPhone? Your own calendars are not touched.`}
            confirmLabel={remove.isPending ? 'Deleting…' : 'Delete them'}
            keepLabel="Cancel"
            busy={remove.isPending}
            onConfirm={() => remove.mutate(undefined)}
          />
        </div>
      )}
      <ErrorNote error={sync.error || remove.error || update.error} />
    </fieldset>
  );
}
