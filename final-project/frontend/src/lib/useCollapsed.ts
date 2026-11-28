import { useState } from 'react';

/**
 * Whether a foldable section is folded, remembered per viewer in this browser.
 * Starts open. Storage can be missing (private window, cleared data), so every
 * read and write is guarded — the section simply opens again then.
 */
export function useCollapsed(key: string): [boolean, () => void] {
  return useStoredFlag(`pc-collapsed-${key}`, false);
}

/** A yes/no choice remembered per viewer in this browser (falls back to ``initial``). */
export function useStoredFlag(storageKey: string, initial: boolean): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(storageKey);
      return v === null ? initial : v === '1';
    } catch { return initial; }
  });
  const toggle = () =>
    setCollapsed((was) => {
      const next = !was;
      try { localStorage.setItem(storageKey, next ? '1' : '0'); } catch { /* convenience only */ }
      return next;
    });
  return [collapsed, toggle];
}
