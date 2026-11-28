import { useEffect, useState } from 'react';
import { useCalendarAutoSync, usePrefs, useProfiles, useYears } from './api/queries';
import { Calculator } from './components/Calculator';
import { Header, tabsFor } from './components/Header';
import { SetupCard } from './components/SetupCard';
import { ErrorNote, Loading } from './components/ui/Feedback';
import { UndoToastHost } from './components/ui/UndoToast';
import { Gallery } from './components/ui/Gallery';
import { applyAppearance } from './lib/appearance';
import { useThemeVersion } from './lib/theme';
import { useUi } from './lib/store';
import { OverviewPage } from './pages/overview/OverviewPage';
import { TransactionsPage } from './pages/transactions/TransactionsPage';
import { CalendarPage } from './pages/calendar/CalendarPage';
import { ForecastPage } from './pages/forecast/ForecastPage';
import { NetWorthPage } from './pages/networth/NetWorthPage';
import { SettingsPage } from './pages/settings/SettingsPage';

export default function App() {
  const profiles = useProfiles();
  const years = useYears();
  const { activeTab, selectedYear, setPeriod, setTab } = useUi();
  const profile = profiles.data?.active;
  useCalendarAutoSync();
  // Charts resolve colours in JavaScript: redraw everything when light/dark changes.
  useThemeVersion();

  // Light / Dark / Match Mac, as saved in Settings: applied at start and on every change.
  const appearance = usePrefs().data?.appearance;
  useEffect(() => {
    if (appearance) applyAppearance(appearance);
  }, [appearance]);

  // Joint (for Isa) lifts every small text to 14px (index.css, [data-profile='joint']).
  useEffect(() => {
    if (profile) document.documentElement.setAttribute('data-profile', profile);
  }, [profile]);

  // Switching to Joint while on a tab Joint does not have opens its Overview.
  useEffect(() => {
    if (profile && !tabsFor(profile).some((t) => t.id === activeTab)) setTab('overview');
  }, [profile, activeTab, setTab]);

  // Pick the year/month to show whenever the open profile's data (re)loads:
  // where the user left off, else today.
  const data = years.data;
  useEffect(() => {
    if (!data || data.needs_setup) return;
    const known = data.years.map((y) => y.year);
    if (selectedYear !== null && known.includes(selectedYear)) return;
    const { last_year, last_month } = data.settings;
    const year = last_year && known.includes(last_year) ? last_year : known.includes(data.current_year) ? data.current_year : known[known.length - 1];
    const month = last_year === year && last_month !== null ? last_month : year === data.current_year ? data.current_month : 0;
    setPeriod(year, month);
  }, [data, selectedYear, setPeriod]);

  // Developer view of the shared parts (#ui-gallery): made-up numbers only.
  const [gallery, setGallery] = useState(() => window.location.hash === '#ui-gallery');
  useEffect(() => {
    const on = () => setGallery(window.location.hash === '#ui-gallery');
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);

  // Until the effect above has run, never show a tab the profile does not have.
  const tab = tabsFor(profile).some((t) => t.id === activeTab) ? activeTab : 'overview';

  let body;
  if (gallery) body = <Gallery />;
  else if (years.isLoading || profiles.isLoading) body = <Loading />;
  else if (years.error || profiles.error) body = <div className="mx-auto max-w-lg p-8"><ErrorNote error={years.error || profiles.error} /></div>;
  else if (data?.needs_setup) body = <SetupCard years={data} />;
  else if (selectedYear === null) body = <Loading />;
  else if (tab === 'overview') body = <OverviewPage year={selectedYear} />;
  else if (tab === 'transactions') body = <TransactionsPage year={selectedYear} />;
  else if (tab === 'calendar') body = <CalendarPage joint={profile === 'joint'} />;
  else if (tab === 'forecast') body = <ForecastPage year={selectedYear} />;
  else if (tab === 'networth') body = <NetWorthPage />;
  else body = <SettingsPage />;

  return (
    <div className="min-h-full">
      <Header years={data} profiles={profiles.data} />
      <main>
        <div className="mx-auto max-w-[1280px] px-6 pb-20 pt-6">{body}</div>
      </main>
      {data && !data.needs_setup && selectedYear !== null && <Calculator />}
      <UndoToastHost />
    </div>
  );
}
