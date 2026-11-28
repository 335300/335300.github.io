import { ChevronDown } from 'lucide-react';

/** The small arrow that folds a section away or opens it again. */
export function FoldButton({ collapsed, onClick, label }: { collapsed: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={!collapsed}
      aria-label={collapsed ? `Open ${label}` : `Fold ${label}`}
      title={collapsed ? 'Show this section' : 'Fold this section away'}
      className="btn-icon btn-sm h-6 w-6 shrink-0 px-0"
    >
      <ChevronDown size={16} aria-hidden className={`transition-transform duration-200 ${collapsed ? '-rotate-90' : ''}`} />
    </button>
  );
}
