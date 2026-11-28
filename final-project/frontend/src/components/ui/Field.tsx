import { CircleX } from 'lucide-react';
import type { ReactNode } from 'react';

/**
 * A form field: label above (12px), the control, then an error line with ×.
 * Use the `.input` class on the control; add `.input-error` when `error` is set
 * and point aria-describedby at `${id}-error`.
 */
export function Field({ id, label, error, hint, children, className = '' }: {
  /** The control's id (label `htmlFor`). */
  id: string;
  label: ReactNode;
  error?: ReactNode;
  /** A short data note under the control ("Today"). */
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col ${className}`}>
      <label className="label" htmlFor={id}>{label}</label>
      {children}
      {error ? <FieldError id={`${id}-error`}>{error}</FieldError> : hint ? <span className="mt-1.5 text-label text-ink-muted">{hint}</span> : null}
    </div>
  );
}

/** "× Use a comma for cents, e.g. 64,18" */
export function FieldError({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <span id={id} role="alert" className="mt-1.5 flex items-center gap-1.5 text-label text-negative">
      <CircleX size={13} className="shrink-0" aria-hidden />
      {children}
    </span>
  );
}
