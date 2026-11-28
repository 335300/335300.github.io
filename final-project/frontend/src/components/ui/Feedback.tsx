import { CircleX } from 'lucide-react';
import { errorMessage } from '../../api/client';
import { Skeleton, useDelayed } from './States';

/** A failed action, under the form that caused it: × icon + the backend's message. */
export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="mt-2 flex items-start gap-1.5 rounded-input bg-negative-tint px-3 py-2 text-label text-negative">
      <CircleX size={14} className="mt-px shrink-0" aria-hidden />
      <span>{errorMessage(error)}</span>
    </p>
  );
}

/** A whole area is loading. Shows nothing for 300 ms, then a quiet placeholder. */
export function Loading({ label = 'Loading…' }: { label?: string }) {
  const show = useDelayed(300);
  if (!show) return <div className="py-10" aria-busy="true" />;
  return (
    <div className="mx-auto max-w-md py-10" aria-busy="true">
      <Skeleton lines={4} label={label} />
      <p className="mt-4 text-[13px] text-ink-muted">{label}</p>
    </div>
  );
}
