import { ChevronDown } from 'lucide-react';
import { useEffect, type ReactNode } from 'react';
import { useCreateYear, useSwitchProfile } from '../api/queries';
import { MONTHS } from '../lib/format';
import { useUi } from '../lib/store';
import type { ProfilesState, Tab, YearsResponse } from '../lib/types';
import { requestAddTransaction, shortcutLabel } from './ui/shortcuts';

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'transactions', label: 'Transactions' },
  { id: 'calendar', label: 'Calendar' },
  { id: 'forecast', label: 'Forecast' },
  { id: 'networth', label: 'Net worth' },
  { id: 'settings', label: 'Settings' },
];

/** Joint is the simple, shared view: no net worth, no settings (the backup covers both profiles). */
const JOINT_TABS: Tab[] = ['overview', 'transactions', 'calendar', 'forecast'];

/** The tabs a profile shows, in header order. */
export const tabsFor = (profile: string | undefined) =>
  profile === 'joint' ? TABS.filter((t) => JOINT_TABS.includes(t.id)) : TABS;

/**
 * The sticky top bar (Style Guide 1): logo, the tabs (⌘1–6), and the month,
 * year and profile choosers. Joint (for Isa) gets bigger tabs and controls
 * and no shortcut hints. Also owns the app shortcuts: ⌘1–6 tabs, ⌘K
 * calculator, ⌘N add a transaction.
 */
export function Header({ years, profiles }: { years?: YearsResponse; profiles?: ProfilesState }) {
  const { activeTab, setTab, selectedYear, selectedMonth, setYear, setMonth, clearPeriod } = useUi();
  const tabs = tabsFor(profiles?.active);
  const joint = profiles?.active === 'joint';
  const switchProfile = useSwitchProfile();
  const createYear = useCreateYear();
  const ready = Boolean(years && !years.needs_setup && selectedYear !== null);
  const known = years?.years.map((y) => y.year) ?? [];
  const nextYear = known.length ? Math.max(...known) + 1 : null;

  useAppShortcuts(ready, tabs.map((t) => t.id));

  const onYear = (value: string) => {
    if (value === 'add' && nextYear) {
      createYear.mutate(nextYear, { onSuccess: () => setYear(nextYear) });
    } else {
      setYear(Number(value));
    }
  };

  return (
    <header className={`drag sticky top-0 z-30 border-b border-line bg-surface ${joint ? 'h-16' : 'h-14'}`}>
      <div className={`flex h-full items-center pl-[84px] pr-5 ${joint ? 'gap-4 min-[1360px]:gap-6' : 'gap-3 min-[1360px]:gap-5'}`}>
        <div className="flex shrink-0 items-center gap-2">
          <Logo size={joint ? 28 : 24} />
          <span className={`font-semibold tracking-tight text-ink ${joint ? 'text-[17px]' : 'text-[15px]'}`}>Centwise</span>
        </div>

        {ready && (
          <nav className={`no-drag flex shrink-0 gap-0.5 bg-neutral-tint p-[3px] ${joint ? 'rounded-[10px]' : 'rounded-lg'}`} aria-label="Main">
            {tabs.map((t, i) => {
              const active = activeTab === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTab(t.id)}
                  aria-current={active ? 'page' : undefined}
                  aria-keyshortcuts={`Meta+${i + 1}`}
                  title={`${t.label} (${shortcutLabel(String(i + 1))})`}
                  // The shortcut hint is drawn by CSS (::after) so the tab's own text stays just its name.
                  // It shows only in wide windows (≥ 1360 px); narrower, the title tooltip still names it.
                  data-key={joint ? undefined : shortcutLabel(String(i + 1))}
                  className={`flex items-center transition-colors duration-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring ${
                    joint ? 'h-[38px] rounded-lg px-3.5 text-[15px] min-[1360px]:px-[18px]' : 'h-[30px] rounded-input px-2.5 text-[13px] after:ml-1.5 after:text-label after:font-medium after:text-ink-muted min-[1360px]:after:content-[attr(data-key)]'
                  } ${active ? 'bg-surface font-semibold text-ink shadow-tab' : 'font-medium text-ink-soft hover:text-ink'}`}
                >
                  {t.label}
                </button>
              );
            })}
          </nav>
        )}

        <div className="no-drag ml-auto flex shrink-0 items-center gap-2">
          {ready && activeTab === 'overview' && (
            <Dropdown label="Month" big={joint} value={String(selectedMonth)} onChange={(v) => setMonth(Number(v))}>
              {MONTHS.map((m, i) => (
                <option key={m} value={i}>{m}</option>
              ))}
            </Dropdown>
          )}
          {ready && (
            <Dropdown label="Year" big={joint} value={String(selectedYear)} onChange={onYear}>
              {known.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
              {nextYear && <option value="add">+ Start {nextYear}</option>}
            </Dropdown>
          )}
          {profiles && (
            <Dropdown
              label="Profile"
              big={joint}
              value={profiles.active}
              onChange={(v) => switchProfile.mutate(v, { onSuccess: clearPeriod })}
            >
              {profiles.profiles.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </Dropdown>
          )}
        </div>
      </div>
    </header>
  );
}

/** ⌘1–6 switch tabs, ⌘K opens/closes the calculator, ⌘N asks the page to add a transaction. */
function useAppShortcuts(ready: boolean, tabIds: Tab[]) {
  const key = tabIds.join(',');
  useEffect(() => {
    if (!ready) return;
    const ids = key.split(',') as Tab[];
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey || e.repeat) return;
      const ui = useUi.getState();
      if (/^[1-6]$/.test(e.key)) {
        const id = ids[Number(e.key) - 1];
        if (!id) return;
        e.preventDefault();
        ui.setTab(id);
      } else if (e.key.toLowerCase() === 'k') {
        e.preventDefault();
        ui.setCalcOpen(!ui.calcOpen);
      } else if (e.key.toLowerCase() === 'n') {
        e.preventDefault();
        if (requestAddTransaction()) return;
        // No page on screen takes it: open Transactions, then ask again once it is there.
        ui.setTab('transactions');
        setTimeout(() => requestAddTransaction(), 50);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [ready, key]);
}

/**
 * A native <select> dressed as the design's dropdown button:
 * "Month  November ▾". Native, so keyboard and VoiceOver work as on any Mac app.
 */
function Dropdown({ label, value, onChange, children, big = false }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: ReactNode;
  /** Joint: 38px tall, 15px text, no prefix word. */
  big?: boolean;
}) {
  return (
    <label
      className={`relative flex cursor-pointer items-center rounded-input border border-line-strong bg-surface text-ink transition-colors duration-hover hover:bg-neutral-tint focus-within:ring-2 focus-within:ring-focus-ring focus-within:ring-offset-2 focus-within:ring-offset-surface ${
        big ? 'h-[38px] rounded-lg pl-3.5 text-[15px]' : 'h-8 pl-2.5 text-[13px]'}`}
    >
      {/* The prefix word hides in windows under 1360 px so the header fits; screen readers still hear it. */}
      {big ? <span className="sr-only">{label}</span> : <span className="mr-2 text-label text-ink-soft max-[1359px]:sr-only">{label}</span>}
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`h-full cursor-pointer appearance-none bg-transparent font-medium text-ink focus:outline-none ${big ? 'pr-8' : 'pr-7'}`}
      >
        {children}
      </select>
      <ChevronDown size={big ? 16 : 14} aria-hidden className={`pointer-events-none absolute text-ink-soft ${big ? 'right-3' : 'right-2'}`} />
    </label>
  );
}

function Logo({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" className="fill-logo" />
      <path d="M21.5 11.2a7 7 0 1 0 0 9.6" fill="none" strokeWidth="3" strokeLinecap="round" className="stroke-on-logo" />
      <circle cx="22.5" cy="16" r="2" className="fill-on-logo" />
    </svg>
  );
}
