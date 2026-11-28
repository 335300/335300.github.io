// Screenshots of every tab, Personal and Joint, on a fresh copy of the sample data.
//
//   cd frontend && npm run build && node scripts/2026-11-28-sample-screens.mjs <out folder> [scratch data folder]
//
// The sample data (../sample-data) is copied into the scratch folder first, so the
// app never changes it. Prints PASS/FAIL per screen and any console errors.

import { _electron as electron } from 'playwright';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const sample = path.resolve(here, '..', '..', 'sample-data');
const [outDir, dataArg] = process.argv.slice(2);
if (!outDir) {
  console.error('usage: node scripts/2026-11-28-sample-screens.mjs <out folder> [scratch data folder]');
  process.exit(2);
}
const dataDir = dataArg || path.join(os.tmpdir(), 'centwise-final-screens');
if (!fs.existsSync(path.join(sample, 'data.json'))) {
  console.error(`No sample data in ${sample} - run ./setup.sh or ./run-sample.sh --new first.`);
  process.exit(1);
}
fs.rmSync(dataDir, { recursive: true, force: true });
fs.cpSync(sample, dataDir, { recursive: true });
fs.mkdirSync(outDir, { recursive: true });

const app = await electron.launch({
  args: ['.'],
  cwd: path.resolve(here, '..'),
  env: { ...process.env, CENTWISE_DATA_DIR: dataDir, CENTWISE_CALENDAR: 'fake' },
});
const win = await app.firstWindow();
const errors = [];
win.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
win.on('pageerror', (e) => errors.push(e.message));
await win.setViewportSize({ width: 1360, height: 900 });
win.setDefaultTimeout(10000);
await win.locator('nav[aria-label="Main"] button').first().waitFor();
await win.waitForTimeout(1500);

let failures = 0;
for (const profile of ['personal', 'joint']) {
  await win.selectOption('header select[aria-label="Profile"]', profile);
  await win.waitForTimeout(1500);
  const tabs = await win.locator('nav[aria-label="Main"] button').allInnerTexts();
  for (const raw of tabs) {
    const name = raw.replace(/⌘\d/g, '').trim().split('\n')[0].trim();
    try {
      await win.locator(`nav[aria-label="Main"] button:has-text("${name}")`).first().click();
      await win.waitForTimeout(1800);
      const text = await win.locator('main').innerText();
      if (text.trim().length < 40) throw new Error('screen is empty');
      if (/Something went wrong|Could not load/i.test(text)) throw new Error('screen shows an error');
      const file = `${profile}-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.png`;
      await win.screenshot({ path: path.join(outDir, file), fullPage: true });
      console.log('PASS', profile, name, '->', file);
    } catch (e) {
      failures++;
      console.log('FAIL', profile, name, '-', e.message.split('\n')[0]);
    }
  }
}
await app.close();
console.log(errors.length ? `Console errors:\n${errors.join('\n')}` : 'Console: no errors');
console.log(failures ? `${failures} screen(s) failed` : 'All screens OK');
process.exit(failures || errors.length ? 1 : 0);
