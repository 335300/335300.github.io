import { useSyncExternalStore } from 'react';

const REDUCE_MOTION = '(prefers-reduced-motion: reduce)';

function subscribe(onChange: () => void) {
  const query = window.matchMedia?.(REDUCE_MOTION);
  query?.addEventListener?.('change', onChange);
  return () => query?.removeEventListener?.('change', onChange);
}

/** True while "Reduce motion" is on in the Mac's settings (updates live). */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, () => window.matchMedia?.(REDUCE_MOTION).matches ?? false, () => false);
}
