import { Info } from 'lucide-react';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

/**
 * The small ⓘ next to a title. Click (or Enter) opens a short explanation;
 * Escape or a click elsewhere closes it. Optional link: "How it's calculated →".
 */
export function HelpPopover({ label, children, moreLabel = 'How it’s calculated →', onMore, align = 'right' }: {
  /** What the help is about ("Kept this month"). Used as the popover title and in the button's name. */
  label: string;
  children: ReactNode;
  moreLabel?: string;
  /** Shows the link when given (e.g. opens the screens guide section or a dialog). */
  onMore?: () => void;
  /** Which edge of the button the popover lines up with. */
  align?: 'left' | 'right';
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey, true);
    };
  }, [open]);

  return (
    <span ref={box} className="relative inline-flex">
      <button
        type="button"
        aria-label={`What is ${label}?`}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen((o) => !o)}
        className="flex h-6 w-6 items-center justify-center rounded-pill text-ink-muted transition-colors duration-hover hover:bg-neutral-tint hover:text-ink-soft"
      >
        <Info size={15} strokeWidth={2} aria-hidden />
      </button>
      {open && (
        <span
          id={id}
          role="dialog"
          aria-label={label}
          className={`absolute top-7 z-40 flex w-[260px] flex-col gap-1.5 rounded-card border border-line bg-surface-raised px-3.5 py-3 text-left shadow-pop ${
            align === 'right' ? 'right-0' : 'left-0'}`}
        >
          <span className="text-[13px] font-semibold text-ink">{label}</span>
          <span className="text-[13px] font-normal leading-[18px] text-ink-soft">{children}</span>
          {onMore && (
            <button type="button" className="self-start text-[13px] font-medium text-primary hover:underline" onClick={() => { setOpen(false); onMore(); }}>
              {moreLabel}
            </button>
          )}
        </span>
      )}
    </span>
  );
}
