/**
 * Display formatting only. Nothing here calculates a financial figure — it
 * turns numbers the backend already computed into text.
 */

const MINUS = '−'; // a real minus sign (U+2212), not a hyphen
const NBSP = '\u00a0'; // no-break space: "12,50 €" never wraps between number and €

/*
 * How things are written (Style Guide: "Amounts are tabular, right-aligned,
 * German-formatted with a no-break space before €"):
 *   money    1.234,56 €   ·   −1.326,48 €   ·   +612 €   ·   8.420 € (round)
 *   percent  71%   ·   0,8%   ·   −8%   ·   +12%   (comma decimals, no space before %)
 *   dates    19.11.2026   ·   19.11. (short)   ·   Thu 19.11. (day)
 *   other    2.170.000 Gs (number first, then the currency label)
 */
const money = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' });
const moneyRound = new Intl.NumberFormat('de-DE', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
});

/** Shown where a figure does not exist (not the same as zero). */
export const NO_DATA = '—';

/**
 * 1.234,56 € — negative values get a real minus sign (U+2212, never a hyphen).
 * `sign: true` adds "+" to amounts above zero (gains, cash in).
 */
export function fmtMoney(value: number, opts: { round?: boolean; sign?: boolean } = {}): string {
  const f = opts.round ? moneyRound : money;
  const text = f.format(Math.abs(value));
  if (value < 0 && text !== f.format(0)) return `${MINUS}${text}`;
  return opts.sign && value > 0 && text !== f.format(0) ? `+${text}` : text;
}

/** fmtMoney, or "—" when the backend sent no figure. */
export function fmtMaybe(value: number | null | undefined, opts: { round?: boolean; sign?: boolean } = {}): string {
  return value === null || value === undefined ? NO_DATA : fmtMoney(value, opts);
}

/** +1.234,56 € / −12,00 € — for amounts whose direction matters. */
export function fmtSigned(value: number, opts: { round?: boolean } = {}): string {
  if (value === 0) return fmtMoney(0, opts);
  return `${value > 0 ? '+' : MINUS}${fmtMoney(Math.abs(value), opts)}`;
}

/** An expense shown as an outflow: −12,00 € (neutral colour, sign carries meaning). */
export function fmtExpense(value: number, opts: { round?: boolean } = {}): string {
  return value === 0 ? fmtMoney(0, opts) : `${MINUS}${fmtMoney(value, opts)}`;
}

const whole = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 0 });

/** An amount in a plan's own currency: "2.170.000 Gs". Euros use the normal format. */
export function fmtLocal(value: number, label: string): string {
  if (label === '€') return fmtMoney(value);
  return `${value < 0 ? MINUS : ''}${whole.format(Math.abs(value))}${NBSP}${label}`;
}

/** A plain number with `digits` decimals, German style: 1.234,5 */
function deNumber(abs: number, digits: number): string {
  return new Intl.NumberFormat('de-DE', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(abs);
}

/** +12% / −8% — a change against a yardstick. */
export function fmtChange(pct: number): string {
  const rounded = Math.round(pct);
  return `${rounded > 0 ? '+' : rounded < 0 ? MINUS : ''}${deNumber(Math.abs(rounded), 0)}%`;
}

/** 12% / 0,8% / −8% (real minus). `sign: true` adds "+" above zero. */
export function fmtPct(value: number, digits = 0, opts: { sign?: boolean } = {}): string {
  const isZero = Number(Math.abs(value).toFixed(digits)) === 0;
  const text = deNumber(Math.abs(value), digits);
  const sign = value < 0 && !isZero ? MINUS : opts.sign && value > 0 && !isZero ? '+' : '';
  return `${sign}${text}%`;
}

/** Compact axis labels: 1,2k € · 12k € · 800 € */
export function fmtAxis(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? MINUS : '';
  if (abs >= 1000) return `${sign}${deNumber(abs / 1000, abs >= 10000 ? 0 : 1)}k${NBSP}€`;
  return `${sign}${deNumber(abs, 0)}${NBSP}€`;
}

const pad2 = (n: number) => String(n).padStart(2, '0');

/** "2026-11-19" → "19.11.2026", or "19.11." with `short`. */
export function fmtDate(iso: string, opts: { short?: boolean } = {}): string {
  const [y, m, d] = iso.split('-').map(Number);
  const dm = `${pad2(d)}.${pad2(m)}.`;
  return opts.short ? dm : `${dm}${y}`;
}

const weekdayFmt = new Intl.DateTimeFormat('en-GB', { weekday: 'short' });

/** "2026-11-18" → "Wed 18.11." */
export function fmtDay(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return `${weekdayFmt.format(new Date(y, m - 1, d))} ${pad2(d)}.${pad2(m)}.`;
}

/** "2036-06" → "June 2036". */
export function fmtMonthYear(ym: string): string {
  const [y, m] = ym.split('-').map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

export const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
export const MONTHS_SHORT = MONTHS.map((m) => m.slice(0, 3));

/**
 * Parse what a person types in an amount box → number (or null if it is not one).
 * German and English writing both work: "12,50", "12.50", "1.234,56", "1,234.56",
 * "1.234" (= one thousand two hundred thirty-four, as the screen writes it),
 * "12 €", and a pasted "−12,50 €" with a real minus sign.
 */
export function parseAmount(raw: string): number | null {
  let s = raw.trim().replace(/[€\s]/g, '').replace(/\u2212/g, '-');
  if (!s) return null;
  const neg = s.startsWith('-');
  const body = s.replace(/^[-+]/, '');
  // Thousands dots only ("1.234", "12.500.000") — how the app itself writes amounts.
  if (/^[1-9]\d{0,2}(\.\d{3})+$/.test(body)) s = `${neg ? '-' : ''}${body.replace(/\./g, '')}`;
  // Thousands commas only, two or more groups ("1,234,567").
  else if (/^[1-9]\d{0,2}(,\d{3}){2,}$/.test(body)) s = `${neg ? '-' : ''}${body.replace(/,/g, '')}`;
  else {
    const lastComma = s.lastIndexOf(',');
    const lastDot = s.lastIndexOf('.');
    if (lastComma > lastDot) s = s.replace(/\./g, '').replace(',', '.');
    else s = s.replace(/,/g, '');
  }
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** Whole amounts in another currency: "2.170.000", "2,170,000" or "2170000" → 2170000;
 *  anything else is read as an ordinary amount. */
export function parseLocalAmount(raw: string): number | null {
  const s = raw.trim().replace(/\s/g, '');
  if (/^\d{1,3}([.,]\d{3})+$/.test(s)) return Number(s.replace(/[.,]/g, ''));
  return parseAmount(s);
}

/** Local date as YYYY-MM-DD. */
export function isoDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
