import type { ReactNode } from 'react';
import { HelpPopover } from './HelpPopover';

export type Tone = 'neutral' | 'positive' | 'negative' | 'brand';

/** Value colour. Teal only for outcomes that are good for the user; red only for real losses. */
const toneClass: Record<Tone, string> = {
  neutral: 'text-ink',
  positive: 'text-positive',
  negative: 'text-negative',
  brand: 'text-ink',
};

/** A comparison the backend already worked out, e.g. "€148 more than your usual month". */
export interface KpiComparison {
  /** ▲ up · ▼ down · = about the same · – nothing to compare */
  direction: 'up' | 'down' | 'same' | 'none';
  /** The words. Always shown — the arrow alone never carries the meaning. */
  text: ReactNode;
  /** Whether the change is good for the user (colours the arrow only). Default neutral. */
  tone?: 'good' | 'bad' | 'neutral';
}

const ARROW: Record<KpiComparison['direction'], string> = { up: '▲', down: '▼', same: '=', none: '–' };
const ARROW_TONE = { good: 'text-positive', bad: 'text-negative', neutral: 'text-ink-soft' };

interface KpiTileProps {
  label: string;
  /** Already formatted (fmtMoney…). */
  value: string;
  /**
   * hero: big number (28px), for 3 tiles in a row · standard (default): 22px, fits 4–6 in a row ·
   * compact: one row, number on the right (20px).
   */
  variant?: 'hero' | 'standard' | 'compact';
  tone?: Tone;
  icon?: ReactNode;
  comparison?: KpiComparison;
  /** A short explanation behind the ⓘ button. */
  help?: ReactNode;
  /** Shows "How it's calculated →" in the help popover. */
  onHelpMore?: () => void;
  /** A data line under the number ("Planned €2,100"). */
  meta?: ReactNode;
  /** Red tint around the tile — for a real problem (negative balance). */
  alert?: boolean;
  testId?: string;
}

/** One headline number. The words under it carry the meaning, not only colour. */
export function KpiTile({ label, value, variant = 'standard', tone = 'neutral', icon, comparison, help, onHelpMore, meta, alert, testId }: KpiTileProps) {
  const frame = `rounded-card border shadow-card ${alert ? 'border-negative bg-negative-tint' : 'border-line bg-surface'}`;
  const labelRow = (
    <span className="flex min-w-0 items-center gap-1.5 text-[13px] font-medium text-ink-soft">
      {icon}
      <span className="truncate">{label}</span>
    </span>
  );

  if (variant === 'compact') {
    return (
      <div className={`${frame} flex items-baseline justify-between gap-3 px-4 py-3`} data-testid={testId}>
        <div className="flex min-w-0 flex-col gap-0.5">
          {labelRow}
          {comparison && <Comparison c={comparison} small />}
          {meta && <span className="num text-label text-ink-soft">{meta}</span>}
        </div>
        <span className={`num shrink-0 whitespace-nowrap text-kpi ${toneClass[tone]}`}>{value}</span>
      </div>
    );
  }

  return (
    <div className={`${frame} relative flex flex-col gap-1.5 ${variant === 'hero' ? 'p-5' : 'px-4 py-4'}`} data-testid={testId}>
      <div className="flex min-h-6 items-center justify-between gap-2">
        {labelRow}
        {help && <HelpPopover label={label} onMore={onHelpMore}>{help}</HelpPopover>}
      </div>
      <span className={`num whitespace-nowrap ${variant === 'hero' ? 'text-display-kpi' : 'text-[22px] font-semibold leading-7 tracking-tight'} ${toneClass[tone]}`}>{value}</span>
      {comparison && <Comparison c={comparison} />}
      {meta && <span className="num text-[13px] leading-[18px] text-ink-soft">{meta}</span>}
    </div>
  );
}

function Comparison({ c, small = false }: { c: KpiComparison; small?: boolean }) {
  return (
    <span className={`num flex items-baseline gap-1.5 text-ink-soft ${small ? 'text-label' : 'text-[13px] leading-[18px]'}`}>
      <span aria-hidden className={`text-label ${small ? 'text-ink-soft' : ARROW_TONE[c.tone ?? 'neutral']}`}>{ARROW[c.direction]}</span>
      <span>{c.text}</span>
    </span>
  );
}
