import { useEffect, useRef } from 'react';

/**
 * App-wide keyboard shortcuts that pages can listen to. The header turns
 * ⌘N into an "add transaction" event; a page that has an add form calls
 * useAddTransactionShortcut(() => open the form). If no page on screen
 * handles it, the header opens the Transactions tab and asks again there.
 */
export const ADD_TRANSACTION_EVENT = 'centwise:add-transaction';

/** Sends the event. Returns true when a page on screen handled it. */
export function requestAddTransaction(): boolean {
  const event = new CustomEvent(ADD_TRANSACTION_EVENT, { cancelable: true });
  return !window.dispatchEvent(event);
}

/** Runs `handler` when the user presses ⌘N (while this component is on screen). */
export function useAddTransactionShortcut(handler: () => void): void {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const on = (e: Event) => {
      e.preventDefault(); // tells the header "handled"
      ref.current();
    };
    window.addEventListener(ADD_TRANSACTION_EVENT, on);
    return () => window.removeEventListener(ADD_TRANSACTION_EVENT, on);
  }, []);
}

/** "⌘1" on a Mac, "Ctrl+1" elsewhere — for hints next to buttons. */
export const shortcutLabel = (key: string) =>
  typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform) ? `⌘${key}` : `Ctrl+${key}`;
