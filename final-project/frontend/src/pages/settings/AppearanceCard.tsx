import { usePrefs, useUpdatePrefs } from '../../api/queries';
import { Card } from '../../components/ui/Card';
import { ErrorNote } from '../../components/ui/Feedback';
import { applyAppearance, currentAppearance, type Appearance } from '../../lib/appearance';
import { useReducedMotion } from './useReducedMotion';

const OPTIONS: { value: Appearance; word: string }[] = [
  { value: 'light', word: 'Light' },
  { value: 'dark', word: 'Dark' },
  { value: 'system', word: 'Match Mac' },
];

/** Settings → Appearance: Light / Dark / Match Mac (saved in prefs, the same for Personal and Joint) and the Motion note. */
export function AppearanceCard() {
  const prefs = usePrefs();
  const update = useUpdatePrefs();
  const reduced = useReducedMotion();
  const chosen = prefs.data?.appearance ?? currentAppearance();

  const pick = (mode: Appearance) => {
    applyAppearance(mode); // right away; the saved choice follows
    if (mode !== prefs.data?.appearance) update.mutate({ appearance: mode });
  };

  return (
    <Card title="Appearance" testId="appearance">
      <div className="flex items-center justify-between gap-3">
        <span id="appearance-theme" className="text-[13px] font-medium text-ink">Theme</span>
        <div role="group" aria-labelledby="appearance-theme" className="flex gap-0.5 rounded-lg bg-neutral-tint p-[3px]">
          {OPTIONS.map((o) => {
            const on = o.value === chosen;
            return (
              <button key={o.value} type="button" aria-pressed={on} onClick={() => pick(o.value)}
                className={`h-7 rounded-input px-3 text-[13px] focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring ${
                  on ? 'bg-surface font-semibold text-ink shadow-card' : 'font-medium text-ink-soft hover:text-ink'}`}>
                {o.word}
              </button>
            );
          })}
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 border-t border-line pt-3">
        <span className="flex flex-col gap-0.5">
          <span className="text-[13px] font-medium text-ink">Motion</span>
          <span className="text-label text-ink-soft">Follows “Reduce motion” in your Mac’s settings.</span>
        </span>
        <span className="shrink-0 text-[13px] text-ink-soft" data-testid="motion-now">Now: {reduced ? 'reduced' : 'normal'}</span>
      </div>
      <ErrorNote error={update.error} />
    </Card>
  );
}
