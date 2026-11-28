import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: 'md' | 'lg' | 'xl';
}

const widths = { md: 'max-w-md', lg: 'max-w-2xl', xl: 'max-w-5xl' };

/** A dialog on a raised surface. Escape or a click outside closes it; focus goes back where it was. */
export function Modal({ title, open, onClose, children, footer, width = 'md' }: ModalProps) {
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Move focus into the dialog (unless a field inside already took it) and give it back on close.
  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    const t = setTimeout(() => {
      if (panel.current && !panel.current.contains(document.activeElement)) panel.current.focus();
    }, 0);
    return () => {
      clearTimeout(t);
      if (before && document.contains(before)) before.focus();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-6" onMouseDown={onClose}>
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`flex max-h-full w-full ${widths[width]} flex-col rounded-card border border-line bg-surface-raised shadow-pop focus:outline-none`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <h2 className="text-card-title">{title}</h2>
          <button className="btn-icon" onClick={onClose} aria-label="Close">
            <X size={16} aria-hidden />
          </button>
        </header>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</footer>}
      </div>
    </div>
  );
}
