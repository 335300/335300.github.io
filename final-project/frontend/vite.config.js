import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Content-Security-Policy for the packaged app.
 *
 * Only style-src is loosened, because Recharts writes inline styles (tooltips,
 * animations) and a strict style-src silently breaks them. connect-src is
 * 'none': the page never makes network requests — the main process does, over
 * IPC. No CDNs, no remote fonts.
 *
 * Injected at build time only; the Vite dev server needs inline scripts for
 * hot reload, so dev runs without it. Always verify the UI on a build.
 */
const CSP = [
  "default-src 'none'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "object-src 'none'",
].join('; ');

const cspPlugin = {
  name: 'centwise-csp',
  apply: 'build',
  transformIndexHtml(html) {
    return html.replace(
      '<meta charset="UTF-8" />',
      `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`
    );
  },
};

export default defineConfig({
  plugins: [react(), cspPlugin],
  // Relative paths so the built page loads from file:// inside the .app.
  base: './',
  build: { outDir: 'dist', emptyOutDir: true, chunkSizeWarningLimit: 1200 },
  server: { host: '127.0.0.1' },
});
