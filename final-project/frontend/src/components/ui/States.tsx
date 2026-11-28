import { useEffect, useState, type ReactNode } from 'react';
import { StatusBadge } from './StatusBadge';

/**
 * Empty, loading and error states (Style Guide 11): calm copy, one next step.
 */

/** Nothing to show yet. Give one next step as `action` (a button), or a short line as children. */
export function EmptyState({ title, children, icon, action, testId }: {
  title: string;
  children?: ReactNode;
  /** Optional 16px icon shown in a 32px circle (e.g. <Plus size={16} />). */
  icon?: ReactNode;
  /** The one next step: a button or two. */
  action?: ReactNode;
  testId?: string;
}) {
  return (
    <div className="flex flex-col items-start gap-2.5 py-5" data-testid={testId}>
      {icon && (
        <span className="flex h-8 w-8 items-center justify-center rounded-pill bg-neutral-tint text-ink-soft" aria-hidden>{icon}</span>
      )}
      <p className="text-card-title text-ink">{title}</p>
      {children && <div className="text-[13px] leading-[18px] text-ink-soft">{children}</div>}
      {action && <div className="mt-1 flex flex-wrap gap-2">{action}</div>}
    </div>
  );
}

/** True only after `ms` — so quick loads never flash a placeholder. */
export function useDelayed(ms = 300): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setReady(true), ms);
    return () => clearTimeout(t);
  }, [ms]);
  return ready;
}

const WIDTHS = ['40%', '60%', '80%', '70%', '55%', '75%'];

/**
 * Grey placeholder blocks while a card loads. Appears only after 300 ms; a soft
 * pulse that is switched off when the Mac asks for reduced motion.
 */
export function Skeleton({ lines = 4, className = '', label = 'Loading…' }: { lines?: number; className?: string; label?: string }) {
  const show = useDelayed(300);
  if (!show) return null;
  return (
    <div className={`flex flex-col gap-2.5 ${className}`} role="status" aria-label={label}>
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={`block rounded bg-neutral-tint motion-safe:animate-pulse ${i === 1 ? 'h-7 rounded-input' : i === 0 ? 'h-3.5' : 'h-3'}`}
          style={{ width: WIDTHS[i % WIDTHS.length] }} />
      ))}
    </div>
  );
}

/** Something could not be done. Calm words, no data lost, one way forward. */
export function ErrorState({ title, children, onRetry, retryLabel = 'Try again', badge = 'Couldn’t finish' }: {
  title: string;
  /** e.g. "No data was lost — all your entries are saved." */
  children?: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
  badge?: string;
}) {
  return (
    <div className="flex flex-col items-start gap-2.5 py-5" role="alert">
      <StatusBadge kind="info">{badge}</StatusBadge>
      <p className="text-card-title text-ink">{title}</p>
      {children && <div className="text-[13px] leading-[18px] text-ink-soft">{children}</div>}
      {onRetry && <button type="button" className="btn-secondary mt-1" onClick={onRetry}>{retryLabel}</button>}
    </div>
  );
}
