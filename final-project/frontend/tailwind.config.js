/**
 * Centwise theme. Colours are *semantic* tokens backed by CSS variables in
 * src/index.css (light + dark). Code says `positive`, `negative`, `warning` —
 * never a hue name or a hex value.
 */
const token = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: token('primary'), hover: token('primary-hover'), tint: token('primary-tint') },
        secondary: { DEFAULT: token('secondary'), tint: token('secondary-tint') },
        gold: { DEFAULT: token('gold'), ink: token('gold-ink') },
        bg: token('bg'),
        surface: { DEFAULT: token('surface'), raised: token('surface-raised') },
        ink: { DEFAULT: token('ink'), soft: token('ink-soft'), muted: token('ink-muted') },
        line: { DEFAULT: token('border'), strong: token('border-strong') },
        track: token('track'),
        positive: { DEFAULT: token('positive'), tint: token('positive-tint') },
        negative: { DEFAULT: token('negative'), tint: token('negative-tint') },
        warning: { DEFAULT: token('warning'), tint: token('warning-tint'), ink: token('warning-ink') },
        info: { DEFAULT: token('info'), tint: token('info-tint') },
        neutral: { tint: token('neutral-tint') },
        logo: token('logo'),
        invest: { DEFAULT: token('invest'), tint: token('invest-tint') },
        'on-primary': token('on-primary'),
        'on-negative': token('on-negative'),
        'on-logo': token('on-logo'),
        'focus-ring': token('focus-ring'),
        scrim: 'rgb(var(--c-scrim) / var(--a-scrim))',
        chart: {
          1: token('chart-1'), 2: token('chart-2'), 3: token('chart-3'), 4: token('chart-4'),
          5: token('chart-5'), 6: token('chart-6'), 7: token('chart-7'), 8: token('chart-8'),
        },
        band50: 'rgb(var(--c-band) / var(--a-band50))',
        band80: 'rgb(var(--c-band) / var(--a-band80))',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Text"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        mono: ['"SF Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
      // Type scale (Style Guide). Small sizes read their weight from --w-sm / --w-table (+100 in dark).
      fontSize: {
        xs: ['12px', { lineHeight: '16px', fontWeight: 'var(--w-sm)' }],
        'display-kpi': ['28px', { lineHeight: '34px', fontWeight: '600', letterSpacing: '-0.01em' }],
        'page-title': ['22px', { lineHeight: '28px', fontWeight: '600' }],
        kpi: ['20px', { lineHeight: '26px', fontWeight: '600' }],
        'card-title': ['16px', { lineHeight: '22px', fontWeight: '600' }],
        body: ['14px', { lineHeight: '20px', fontWeight: '400' }],
        table: ['13px', { lineHeight: '18px', fontWeight: 'var(--w-table)' }],
        label: ['12px', { lineHeight: '16px', fontWeight: 'var(--w-sm)' }],
      },
      borderRadius: {
        input: '6px',
        card: '12px',
        pill: '999px',
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        raised: 'var(--shadow-raised)',
        pop: 'var(--shadow-pop)',
        tab: 'var(--shadow-tab)',
      },
      transitionDuration: { hover: '120ms' },
    },
  },
  plugins: [],
};
