import { Calculator as CalculatorIcon, Check, Copy, Delete, X } from 'lucide-react';
import { useDeferredValue, useEffect, useRef, useState } from 'react';
import { errorMessage } from '../api/client';
import { useCalc } from '../api/queries';
import { useUi } from '../lib/store';
import { FieldError } from './ui/Field';
import { shortcutLabel } from './ui/shortcuts';

const KEYS: { label: string; put?: string; action?: 'clear' | 'equals'; look?: 'op' | 'main' }[] = [
  { label: 'C', action: 'clear', look: 'op' }, { label: '(', look: 'op' }, { label: ')', look: 'op' }, { label: '÷', look: 'op' },
  { label: '7' }, { label: '8' }, { label: '9' }, { label: '×', look: 'op' },
  { label: '4' }, { label: '5' }, { label: '6' }, { label: '−', look: 'op' },
  { label: '1' }, { label: '2' }, { label: '3' }, { label: '+', look: 'op' },
  { label: '%', look: 'op' }, { label: '0' }, { label: '.' }, { label: '=', action: 'equals', look: 'main' },
];

const grouped = new Intl.NumberFormat('en-IE', { maximumFractionDigits: 10 });

/**
 * A pocket calculator, one click away on every tab. It floats above the page
 * (and above dialogs), keeps what you typed while you move between tabs, and
 * leaves the arithmetic to the backend — the page never adds money up itself.
 */
export function Calculator() {
  const { calcOpen: open, calcText: text, setCalcOpen: setOpen, setCalcText: setText } = useUi();
  const input = useRef<HTMLInputElement>(null);
  const [asked, setAsked] = useState(false); // "=" was pressed: now an unfinished sum is worth an error
  const [copied, setCopied] = useState(false);
  const calc = useCalc(useDeferredValue(text));
  const answer = text.trim() && calc.data && calc.data.expression === text.trim() ? calc.data : null;

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(t);
  }, [copied]);

  const change = (next: string) => {
    setText(next);
    setAsked(false);
  };
  const equals = () => {
    if (answer) change(answer.text);
    else setAsked(true);
  };
  const press = (key: (typeof KEYS)[number]) => {
    if (key.action === 'clear') change('');
    else if (key.action === 'equals') equals();
    else change(text + (key.put ?? key.label));
    input.current?.focus();
  };
  const copy = async () => {
    if (!answer) return;
    try {
      await navigator.clipboard.writeText(answer.text);
      setCopied(true);
    } catch {
      /* the clipboard is a convenience; the result is on screen either way */
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-[60] flex flex-col items-end gap-3">
      {open && (
        <section
          role="dialog"
          aria-label="Calculator"
          className="w-72 rounded-card border border-line bg-surface-raised p-3 shadow-pop"
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.stopPropagation();
              setOpen(false);
            }
          }}
        >
          <header className="mb-2 flex items-center justify-between">
            <h2 className="text-body font-semibold">Calculator <span className="ml-1 text-label text-ink-soft">{shortcutLabel('K')}</span></h2>
            <button className="btn-icon h-7" aria-label="Close calculator" onClick={() => setOpen(false)}><X size={16} aria-hidden /></button>
          </header>
          <div className="rounded-lg border border-line-strong bg-surface px-2.5 py-2 focus-within:ring-2 focus-within:ring-focus-ring focus-within:ring-offset-2 focus-within:ring-offset-surface-raised">
            <div className="flex items-center gap-1">
              <input
                ref={input}
                aria-label="Calculation"
                className="num w-full bg-transparent text-right text-body text-ink-soft placeholder:text-ink-muted focus:outline-none focus-visible:outline-none"
                placeholder="1650 + 300"
                value={text}
                spellCheck={false}
                autoComplete="off"
                onChange={(e) => change(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    equals();
                  }
                }}
              />
              <button className="btn-icon h-7 px-1" aria-label="Delete last character" onClick={() => { change(text.slice(0, -1)); input.current?.focus(); }}>
                <Delete size={15} aria-hidden />
              </button>
            </div>
            <div className="mt-1 flex h-7 items-center justify-end gap-1.5">
              {answer ? (
                <>
                  <output className="num truncate text-xl font-semibold text-ink" aria-label="Result">= {grouped.format(answer.result)}</output>
                  <button className="btn-icon h-7 px-1" aria-label="Copy result" title="Copy the result" onClick={copy}>
                    {copied ? <Check size={15} className="text-positive" aria-hidden /> : <Copy size={15} aria-hidden />}
                  </button>
                </>
              ) : (
                <span className="num text-xl font-semibold text-ink-muted">{text.trim() ? '…' : '0'}</span>
              )}
            </div>
          </div>
          {asked && !answer && calc.error && <FieldError>{errorMessage(calc.error)}</FieldError>}
          <div className="mt-2 grid grid-cols-4 gap-1.5">
            {KEYS.map((key) => (
              <button
                key={key.label}
                type="button"
                onClick={() => press(key)}
                aria-label={key.action === 'clear' ? 'Clear' : key.action === 'equals' ? 'Equals' : key.label}
                className={`num h-9 rounded-input text-body font-medium transition-colors duration-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface-raised ${
                  key.look === 'main'
                    ? 'bg-primary font-semibold text-on-primary hover:bg-primary-hover'
                    : key.look === 'op'
                      ? 'bg-primary-tint text-primary hover:bg-primary/20'
                      : 'border border-line-strong bg-surface text-ink hover:bg-neutral-tint'
                }`}
              >
                {key.label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-label text-ink-soft">Type 12,50 or 12.50 · 15% = 0.15 · Enter = result</p>
        </section>
      )}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-label={open ? 'Hide calculator' : 'Open calculator'}
        aria-expanded={open}
        aria-keyshortcuts="Meta+K"
        title={`Calculator (${shortcutLabel('K')})`}
        className="flex h-12 w-12 items-center justify-center rounded-pill bg-primary text-on-primary shadow-pop transition-colors duration-hover hover:bg-primary-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
      >
        <CalculatorIcon size={20} aria-hidden />
      </button>
    </div>
  );
}
