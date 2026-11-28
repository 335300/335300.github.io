import { X } from 'lucide-react';
import { useEffect } from 'react';
import { create } from 'zustand';

/**
 * "3 transactions deleted. Undo" — one message at a time, bottom centre (clear
 * of the calculator), gone after 10 seconds. Call showUndo() after a delete;
 * <UndoToastHost /> is rendered once in App.tsx.
 */
interface Toast {
  id: number;
  message: string;
  onUndo?: () => void;
  undoLabel: string;
  duration: number;
}

const useToast = create<{ toast: Toast | null; set: (t: Toast | null) => void }>((set) => ({
  toast: null,
  set: (toast) => set({ toast }),
}));

let nextId = 1;

export function showUndo(message: string, onUndo?: () => void, opts: { undoLabel?: string; duration?: number } = {}): void {
  useToast.getState().set({ id: nextId++, message, onUndo, undoLabel: opts.undoLabel ?? 'Undo', duration: opts.duration ?? 10_000 });
}

export function hideUndo(): void {
  useToast.getState().set(null);
}

export function UndoToastHost() {
  const { toast, set } = useToast();

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => set(null), toast.duration);
    return () => clearTimeout(t);
  }, [toast, set]);

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-5 z-[70] flex justify-center px-24" aria-live="polite" role="status">
      {toast && (
        <div key={toast.id} data-testid="undo-toast"
          className="pointer-events-auto flex items-center gap-3 rounded-card border border-line bg-surface-raised py-2 pl-4 pr-2 text-[13px] text-ink shadow-pop">
          <span>{toast.message}</span>
          {toast.onUndo && (
            <button type="button" className="btn-ghost h-7 px-2"
              onClick={() => { const undo = toast.onUndo; set(null); undo?.(); }}>
              {toast.undoLabel}
            </button>
          )}
          <button type="button" className="btn-icon h-7" aria-label="Dismiss" onClick={() => set(null)}>
            <X size={14} aria-hidden />
          </button>
        </div>
      )}
    </div>
  );
}
