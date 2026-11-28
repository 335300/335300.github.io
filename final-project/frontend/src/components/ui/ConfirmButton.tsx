import { useEffect, useRef, useState } from 'react';

/**
 * A destructive action that asks once, in place (Style Guide 9):
 *   [Delete 3 transactions…]  →  "Delete 3 transactions? You can undo for 10 seconds."  [Keep] [Delete]
 * Pair it with showUndo() (UndoToast) after the delete went through.
 */
export function ConfirmButton({ label, question, confirmLabel = 'Delete', keepLabel = 'Keep', onConfirm, compact = false, disabled = false, busy = false, testId, ariaLabel }: {
  /** The button before asking: "Delete 3 transactions…" */
  label: string;
  /** The question: "Delete 3 transactions? You can undo for 10 seconds." */
  question: string;
  confirmLabel?: string;
  keepLabel?: string;
  onConfirm: () => void;
  /** 24px buttons, for table rows. */
  compact?: boolean;
  disabled?: boolean;
  busy?: boolean;
  testId?: string;
  /** Accessible name when the visible label alone is not enough ("Delete account Tagesgeld"). */
  ariaLabel?: string;
}) {
  const [asking, setAsking] = useState(false);
  const keep = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (asking) keep.current?.focus();
  }, [asking]);

  if (!asking) {
    return (
      <button type="button" className={`btn-danger ${compact ? 'btn-sm' : ''}`} disabled={disabled || busy}
        onClick={() => setAsking(true)} data-testid={testId} aria-label={ariaLabel}>
        {label}
      </button>
    );
  }
  return (
    <div
      role="group"
      aria-label={question}
      className={`inline-flex items-center gap-2 rounded-lg bg-negative-tint text-ink ${compact ? 'py-0.5 pl-2 pr-0.5' : 'py-1 pl-3 pr-1'}`}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation();
          setAsking(false);
        }
      }}
    >
      <span className={compact ? 'text-label' : 'text-[13px]'}>{question}</span>
      <button ref={keep} type="button" className={`btn-secondary ${compact ? 'btn-sm' : 'h-7 px-2.5'}`} onClick={() => setAsking(false)}>
        {keepLabel}
      </button>
      <button type="button" className={`btn-danger-solid ${compact ? 'btn-sm' : 'h-7 px-2.5'}`} disabled={busy}
        onClick={() => { setAsking(false); onConfirm(); }}>
        {confirmLabel}
      </button>
    </div>
  );
}
