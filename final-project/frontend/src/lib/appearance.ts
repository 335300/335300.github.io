/**
 * Light / Dark / Match Mac. The colours themselves live in src/index.css; this
 * only sets (or removes) data-theme on <html>. The Settings screen calls it
 * with the saved choice; charts redraw by themselves (lib/theme.ts).
 */
export type Appearance = 'system' | 'light' | 'dark';

export function applyAppearance(mode: Appearance): void {
  const root = document.documentElement;
  if (mode === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', mode);
}

/** The choice currently applied ("system" when nothing is forced). */
export function currentAppearance(): Appearance {
  const v = document.documentElement.getAttribute('data-theme');
  return v === 'light' || v === 'dark' ? v : 'system';
}
