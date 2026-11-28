import { ArrowRight } from 'lucide-react';
import type { ReactNode } from 'react';
import { useCollapsed } from '../../lib/useCollapsed';
import { FoldButton } from './FoldButton';
import { HelpPopover } from './HelpPopover';

interface CardProps {
  title?: ReactNode;
  /** One short line under the title. Personal screens: data only, no explanations. */
  subtitle?: ReactNode;
  /** Small quiet text on the right of the title row ("next 14 days"). */
  meta?: ReactNode;
  /** A short explanation behind an ⓘ next to the title (needs a plain-text `helpLabel` or string title). */
  help?: ReactNode;
  helpLabel?: string;
  /** Buttons on the right of the title row. */
  action?: ReactNode;
  children: ReactNode;
  /** Left side of the footer row, e.g. "Total −€1,326.48" (already formatted). */
  footer?: ReactNode;
  /** Right side of the footer row: "Open calendar →". */
  link?: { label: string; onClick: () => void; testId?: string };
  className?: string;
  bodyClassName?: string;
  /** Makes the card foldable: an arrow in the header hides the content; the state is remembered under this key. */
  collapseKey?: string;
  /** Plain-text name of the card for the fold button ("Income calendar"). */
  collapseLabel?: string;
  testId?: string;
}

export function Card({ collapseKey, ...props }: CardProps) {
  return collapseKey ? <FoldableCard collapseKey={collapseKey} {...props} /> : <CardFrame {...props} collapsed={false} />;
}

function FoldableCard({ collapseKey, ...props }: CardProps & { collapseKey: string }) {
  const [collapsed, toggle] = useCollapsed(collapseKey);
  return (
    <CardFrame {...props} collapsed={collapsed}
      fold={<FoldButton collapsed={collapsed} onClick={toggle} label={props.collapseLabel ?? 'section'} />} />
  );
}

function CardFrame({ title, subtitle, meta, help, helpLabel, action, children, footer, link, className = '', bodyClassName = '', collapsed, fold, testId }: CardProps & {
  collapsed: boolean;
  fold?: ReactNode;
}) {
  const hasHeader = Boolean(title || action || fold || meta);
  const hasFooter = !collapsed && Boolean(footer || link);
  const label = helpLabel ?? (typeof title === 'string' ? title : 'this card');
  return (
    <section className={`flex flex-col rounded-card border border-line bg-surface shadow-card ${className}`}
      data-collapsed={collapsed || undefined} data-testid={testId}>
      {hasHeader && (
        <header className={`flex items-start justify-between gap-3 px-5 pt-4 ${collapsed ? 'pb-4' : ''}`}>
          <div className="min-w-0">
            <div className="flex min-h-6 items-center gap-1.5">
              {title && <h2 className="text-card-title text-ink">{title}</h2>}
              {help && <HelpPopover label={label} align="left">{help}</HelpPopover>}
            </div>
            {subtitle && !collapsed && <p className="mt-0.5 text-[13px] leading-[18px] text-ink-soft">{subtitle}</p>}
          </div>
          <div className="flex min-h-6 shrink-0 items-center gap-2">
            {meta && !collapsed && <span className="num text-label text-ink-muted">{meta}</span>}
            {!collapsed && action}
            {fold}
          </div>
        </header>
      )}
      {!collapsed && <div className={`flex-1 px-5 ${hasFooter ? 'pb-2' : 'pb-5'} ${hasHeader ? 'pt-3' : 'pt-5'} ${bodyClassName}`}>{children}</div>}
      {hasFooter && (
        <footer className="flex items-center justify-between gap-3 px-5 pb-4 pt-3">
          <span className="num text-[13px] text-ink-soft">{footer}</span>
          {link && (
            <button type="button" onClick={link.onClick} data-testid={link.testId}
              className="inline-flex items-center gap-1 rounded-input text-[13px] font-medium text-primary hover:underline">
              {link.label.replace(/\s*→$/, '')}
              <ArrowRight size={14} aria-hidden />
            </button>
          )}
        </footer>
      )}
    </section>
  );
}

/** A short note next to a number. Personal screens: keep it to data, warnings and edit notes. */
export function Hint({ children }: { children: ReactNode }) {
  return <p className="text-[13px] leading-[18px] text-ink-soft">{children}</p>;
}

export { EmptyState } from './States';
