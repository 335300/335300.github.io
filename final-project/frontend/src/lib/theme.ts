/**
 * Chart colours. Recharts sets SVG attributes, which cannot read CSS variables,
 * so this resolves the same tokens from src/index.css at runtime. Charts use
 * these — never hex literals.
 *
 * Light and dark mode give the tokens different values, so the resolved values
 * are cached only until the colour scheme changes (Mac setting, or the
 * data-theme attribute on <html>). Components that draw with color() call
 * useThemeVersion() so they redraw when that happens.
 */
import { useSyncExternalStore } from 'react';

export type Token =
  | 'primary' | 'primary-tint' | 'secondary' | 'gold' | 'gold-ink'
  | 'ink' | 'ink-soft' | 'ink-muted' | 'border' | 'border-strong' | 'track'
  | 'positive' | 'negative' | 'warning' | 'warning-ink' | 'info'
  | 'surface' | 'surface-raised' | 'bg' | 'neutral-tint' | 'invest'
  | 'chart-1' | 'chart-2' | 'chart-3' | 'chart-4' | 'chart-5' | 'chart-6' | 'chart-7' | 'chart-8'
  | 'band50' | 'band80';

/** Categorical chart colours in order (chart-8 is the grey "Other"). */
export const CHART_TOKENS = ['chart-1', 'chart-2', 'chart-3', 'chart-4', 'chart-5', 'chart-6', 'chart-7', 'chart-8'] as const;

const cache = new Map<string, string>();
let version = 0;
const listeners = new Set<() => void>();

function read(name: string): string {
  let v = cache.get(name);
  if (v === undefined) {
    v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    cache.set(name, v);
  }
  return v;
}

export function color(token: Token, alpha = 1): string {
  if (token === 'band50' || token === 'band80') {
    // The bands are primary-family at a fixed opacity; `alpha` scales it further.
    const base = Number(read(token === 'band50' ? '--a-band50' : '--a-band80')) || 0.2;
    return `rgb(${read('--c-band')} / ${base * alpha})`;
  }
  const channels = read(`--c-${token}`);
  return alpha === 1 ? `rgb(${channels})` : `rgb(${channels} / ${alpha})`;
}

function invalidate() {
  cache.clear();
  version += 1;
  listeners.forEach((l) => l());
}

let watching = false;
function watch() {
  if (watching || typeof window === 'undefined') return;
  watching = true;
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', invalidate);
  new MutationObserver(invalidate).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'data-profile'],
  });
}

function subscribe(listener: () => void) {
  watch();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** A number that changes whenever light/dark changes; call it in any component that uses color(). */
export function useThemeVersion(): number {
  return useSyncExternalStore(subscribe, () => version, () => version);
}

/** True when the dark values are in use right now. */
export function isDark(): boolean {
  const forced = document.documentElement.getAttribute('data-theme');
  if (forced === 'dark') return true;
  if (forced === 'light') return false;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}
