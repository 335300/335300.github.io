import type { ReactNode } from 'react';

/** Shared hover card so every chart looks the same: raised surface, label left, value right. */
export function TooltipCard({ title, rows }: { title: ReactNode; rows: { label: string; value: string; swatch?: string; dashed?: boolean }[] }) {
  return (
    <div className="min-w-[180px] rounded-lg border border-line bg-surface-raised px-3 py-2.5 shadow-pop">
      <div className="mb-1.5 text-[13px] font-semibold text-ink">{title}</div>
      <div className="flex flex-col gap-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-4 text-label">
            <span className="flex items-center gap-1.5 text-ink-soft">
              {r.swatch && (
                <span
                  aria-hidden
                  className="inline-block h-0.5 w-3"
                  style={{ background: r.dashed ? 'transparent' : r.swatch, borderTop: r.dashed ? `2px dashed ${r.swatch}` : undefined }}
                />
              )}
              {r.label}
            </span>
            <span className="num font-semibold text-ink">{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
