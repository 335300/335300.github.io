/**
 * Dev helper: drive a fresh install through every write flow in the
 * built app and check what the screen shows. Throwaway data folder only.
 *
 *   node scripts/e2e.mjs <out-dir> <empty-data-dir>
 *
 * Money on screen is German style: "1.234,56 €" with a no-break space before €,
 * a real minus sign (−), "71%", "19.11.2026" and "2.170.000 Gs". The helpers
 * eur() and gs() write the expected texts that way.
 */
import { _electron as electron } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const [outDir, dataDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
fs.rmSync(dataDir, { recursive: true, force: true });

// Test-only: the Save window writes into saveDir, the Open window returns the backup made there.
const saveDir = path.join(outDir, 'saved');
fs.rmSync(saveDir, { recursive: true, force: true });
fs.mkdirSync(saveDir, { recursive: true });
const pad = (n) => String(n).padStart(2, '0');
const now = new Date();
const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
const backupFile = path.join(saveDir, `${todayIso}-personal-centwise-backup.pcbackup`);
const app = await electron.launch({
  ...(process.env.EXE ? { executablePath: process.env.EXE, args: [] } : { args: ['.'] }),
  // CENTWISE_CALENDAR=fake: made-up calendar events; the check never reads a real Apple Calendar.
  env: { ...process.env, CENTWISE_DATA_DIR: dataDir, CENTWISE_CALENDAR: 'fake', CENTWISE_E2E_SAVE_DIR: saveDir, CENTWISE_E2E_OPEN_FILE: backupFile },
});
const win = await app.firstWindow();
const errors = [];
win.on('console', (m) => ['error', 'warning'].includes(m.type()) && errors.push(`[${m.type()}] ${m.text()}`));
win.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`));
await win.setViewportSize({ width: 1360, height: 900 });
win.setDefaultTimeout(8000);
await win.waitForTimeout(1000);

let failures = 0;
const check = async (label, fn) => {
  try { await fn(); console.log('PASS', label); }
  catch (e) { failures++; console.log('FAIL', label, '-', e.message.split('\n')[0], (e.stack.match(/e2e.mjs:\d+/g) || []).join(',')); await shot('fail-' + failures).catch(() => {}); }
};
const shot = (n) => win.screenshot({ path: path.join(outDir, `${n}.png`), fullPage: true });
const text = () => win.locator('main').innerText();
const expectText = async (s) => {
  await win.getByText(s, { exact: false }).first().waitFor({ timeout: 4000 });
};

// -- How the screen writes things -----------------------------------------------
const NB = ' '; // no-break space
const M = '−'; // real minus sign
const eur = (s) => `${s}${NB}€`; // eur('−2.100,00') → "−2.100,00 €"
const gs = (s) => `${s}${NB}Gs`; // gs('2.170.000') → "2.170.000 Gs"
const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// -- Moving around ----------------------------------------------------------------
const tab = (name) => win.click(`nav[aria-label="Main"] button:has-text("${name}")`);
const profile = (id) => win.selectOption('header select[aria-label="Profile"]', id);
/** Overview with a month picked in the header (0–11). The month stays for the other tabs. */
const overviewMonth = async (m) => {
  await tab('Overview');
  await win.selectOption('header select[aria-label="Month"]', String(m));
};
/** Transactions as a table of the whole year (Personal). */
const txAll = async () => {
  await tab('Transactions');
  await win.getByRole('radio', { name: 'Table' }).click();
  await win.selectOption('main label:has-text("Month") select', '');
};
const txCount = (n) => win.getByTestId('transactions-subtitle').filter({ hasText: `${n} transaction` }).waitFor({ timeout: 4000 });
/** "Add transaction" (Personal) or "Add a payment" (Joint): the form opens in a window. */
const addTx = async ({ type = 'expense', date, amount, cat, desc = '', oneOff = false, foreign }) => {
  await win.getByRole('button', { name: /^Add (transaction|a payment)/ }).first().click();
  const dlg = win.getByRole('dialog', { name: /^Add a (transaction|payment)$/ });
  await dlg.getByRole('radio', { name: type === 'income' ? '+ Income' : '− Expense' }).click();
  await dlg.locator('#modal-tx-date').fill(date);
  await dlg.locator('#modal-tx-amount').fill(amount);
  await dlg.locator('#modal-tx-cat').fill(cat);
  if (foreign) await dlg.locator('#modal-tx-foreign').fill(foreign);
  await dlg.locator('#modal-tx-desc').fill(desc);
  if (oneOff) await dlg.locator('#modal-tx-oneoff').check();
  await dlg.getByRole('button', { name: `Add ${type}` }).click();
  await dlg.getByText('✓ Added').waitFor({ timeout: 4000 });
  await win.keyboard.press('Escape');
  await dlg.waitFor({ state: 'detached', timeout: 4000 });
};
/** Transactions → Categories window: run `fn` with it, then close it. */
const withCategories = async (fn) => {
  await win.getByRole('button', { name: 'Categories', exact: true }).click();
  const dlg = win.getByRole('dialog', { name: 'Categories' });
  await fn(dlg);
  await dlg.getByRole('button', { name: 'Close', exact: true }).first().click();
  await dlg.waitFor({ state: 'detached', timeout: 4000 });
};
const current = () => win.locator('nav[aria-label="Main"] button[aria-current="page"]').innerText();

await check('setup card', async () => {
  await win.selectOption('#setup-month', '0');
  await win.fill('#setup-year', '2026');
  await win.fill('#setup-balance', '1.000,50');
  await win.click('button:has-text("Get started")');
  await expectText('Cash in vs cash out');
});

await check('add single expense + income', async () => {
  await tab('Transactions');
  // The table is the first view; the calendar stays one click away (and is remembered).
  await win.locator('[role=radio][aria-checked="true"]', { hasText: 'Table' }).waitFor({ timeout: 4000 });
  // No form on the page itself: "Add transaction" opens it in a window.
  if (await win.locator('#modal-tx-amount').count()) throw new Error('the add form should open in a window');
  await addTx({ date: '2026-10-02', amount: '650', cat: 'Rent', desc: 'October rent' });
  await win.selectOption('main label:has-text("Month") select', '');
  await expectText('October rent');
  await addTx({ type: 'income', date: '2026-10-02', amount: '2100', cat: 'Salary' });
  await expectText(eur('+2.100,00'));
});

await check('quick entry: paste rows, save all together', async () => {
  const qe = win.getByTestId('quick-entry');
  await qe.getByRole('button', { name: 'Paste from a spreadsheet' }).click();
  await qe.getByLabel('Pasted rows').fill('03.10.2026; 12,40; Groceries; Bakery\n04.10.2026; expense; 230; Groceries; Supermarket\n05.10.2026; income; 80; Other income; Sold a lamp');
  await qe.getByRole('button', { name: 'Fill the rows' }).click();
  await shot('40-bulk');
  await qe.getByRole('button', { name: /^Save 3 rows/ }).click();
  await qe.getByText('✓ Saved 3 transactions').waitFor({ timeout: 4000 });
  await expectText('Sold a lamp');
  await txCount(5);
});

await check('overview reflects new data', async () => {
  await overviewMonth(9);
  await win.locator('main h1', { hasText: 'Overview' }).waitFor({ timeout: 4000 });
  await expectText('October 2026');
  const t = await text();
  // Cash in 2180, cash out 892.40; kept 1287.60 shows in whole euros on the big tile.
  for (const s of [eur('+2.180,00'), eur(`${M}892,40`), eur('+1.288')]) if (!t.includes(s)) throw new Error(`missing ${s}`);
  // First month with data: no earlier month to compare with, so no "above/below usual" anywhere,
  // no "Planned 0 €" (nothing planned) and no "Usual month 0,00 €" in the cost trends.
  await win.getByTestId('kpi-kept').getByText('No earlier months yet').waitFor({ timeout: 4000 });
  for (const s of ['usual month', 'above usual', 'below usual', 'Planned ', 'Usual month (middle']) {
    if (t.includes(s)) throw new Error(`fresh profile should not show "${s}"`);
  }
  await shot('41-overview');
});

await check('budget edit shows "Close to limit"', async () => {
  await tab('Forecast');
  const cell = win.getByLabel('Groceries budget Oct');
  await cell.fill('300');
  await cell.press('Tab');
  await win.getByLabel('Salary budget Nov').fill('2100');
  await win.getByLabel('Salary budget Nov').press('Tab');
  await win.getByLabel('Salary budget Dec').fill('2100');
  await win.getByLabel('Salary budget Dec').press('Tab');
  await win.waitForTimeout(500);
  await tab('Overview');
  // 242.40 / 300 = 81%
  await win.getByTestId('budget-row-Groceries').getByText('Close to limit').waitFor({ timeout: 4000 });
});

await check('goal + contribution', async () => {
  await tab('Forecast');
  await win.click('button:has-text("New goal")');
  await win.fill('#goal-name', 'Laptop');
  await win.fill('#goal-target', '900');
  await win.fill('#goal-date', '2027-03-31');
  await win.click('button:has-text("Create goal")');
  await expectText('Laptop');
  await win.click('button:has-text("Add money")');
  await win.getByLabel('Contribution amount').fill('300');
  await win.click('button:has-text("Add to Laptop")');
  await expectText('33% saved');
  await expectText('On track');
  await shot('42-forecast');
});

await check('investment plan + payment', async () => {
  await win.click('button:has-text("New plan")');
  if ((await win.locator('#inv-amount').getAttribute('placeholder')) !== '2.170.000') throw new Error('amount placeholder is not German style');
  await win.fill('#inv-name', 'Plot of land');
  await win.fill('#inv-cat', 'Land');
  await win.fill('#inv-unit', 'cuota');
  await win.fill('#inv-cur', 'Gs');
  await win.fill('#inv-amount', '2.170.000');
  await win.fill('#inv-total', '130');
  await win.fill('#inv-paid', '15');
  await win.fill('#inv-cost', '340');
  await win.click('button:has-text("Create plan")');
  await expectText('of 130 cuotas paid');
  await expectText(gs('32.550.000')); // 15 × 2,170,000
  await win.click('button:has-text("Record a payment")');
  await win.getByLabel('Payment date').fill('2026-10-06');
  await win.getByLabel('Payment amount').fill('332');
  await win.click('button:has-text("Save payment")');
  await expectText(gs('34.720.000')); // 16 × 2,170,000
  await shot('44-forecast-investment');
});

await check('overview: investment is cash out, not an expense', async () => {
  await tab('Overview');
  await expectText('Paid in October');
  const t = await text();
  // cash out 892.40 costs + 332 invested; kept 2180 − 1224.40 = 955.60; wealth built 2180 − 892.40 = 1287.60
  // liquidity = balance (1000.50 + 2180 − 1224.40 = 1956.10): nothing is saved for a goal up to October yet
  for (const s of [eur(`${M}1.224,40`), `${eur('892')} costs · ${eur('332')} invested`, eur('+956'), eur('+1.288'), 'Plot of land', 'Liquidity']) {
    if (!t.includes(s)) throw new Error(`missing ${s}`);
  }
  await win.getByTestId('kpi-liquidity').getByText(eur('1.956')).waitFor({ timeout: 4000 });
  await win.getByTestId('kpi-balance').getByText(eur('1.956,10')).waitFor({ timeout: 4000 });
});

await check('distribute the month\'s savings to goals', async () => {
  await expectText('has no job yet');
  await win.click('button:has-text("Distribute to goals")');
  await win.getByLabel('Amount for Laptop').fill('200');
  await win.getByRole('dialog').getByText(eur('755,60')).first().waitFor({ timeout: 4000 }); // 955.60 − 200, computed by the backend preview
  await win.click('button:has-text("Put toward goals")');
  await expectText(`${eur('200,00')} to goals · ${eur('755,60')} not assigned`);
  await expectText(`+${eur('200,00')} in October`);
  // Saving for a goal keeps the balance and lowers the liquidity: 1956.10 − 200.
  await expectText(`${eur('200,00')} of your balance is saved for goals · ${eur('1.756,10')} is liquid`);
  await shot('45-overview-distribution');
});

await check('transactions: quick entry above the list, bills and rules beside it', async () => {
  await txAll();
  await expectText('1 cuota');
  const entry = await win.getByTestId('quick-entry').boundingBox();
  const list = await win.getByTestId('transactions-list').boundingBox();
  const bills = await win.getByTestId('recurring-bills').boundingBox();
  if (!(entry.y < list.y)) throw new Error('quick entry should sit above the list');
  if (!(bills.x > list.x + list.width - 2)) throw new Error('bills should sit right of the list');
});

await check('delete transaction with inline confirm', async () => {
  const row = win.locator('tr', { hasText: 'Bakery' });
  await row.hover();
  await row.getByLabel('Delete', { exact: true }).click();
  await row.getByRole('button', { name: 'Delete', exact: true }).click();
  await txCount(5);
  await win.getByTestId('undo-toast').getByText('Transaction deleted.').waitFor({ timeout: 4000 });
});

await check('transactions calendar: a day shows its movements, a click opens them', async () => {
  await win.getByRole('radio', { name: 'Calendar' }).click();
  const cal = win.getByTestId('transactions-calendar');
  const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const shown = MONTH_NAMES.indexOf((await win.getByTestId('calendar-month').innerText()).split(' ')[0]);
  for (let i = shown; i !== 9; i += i > 9 ? -1 : 1) await win.getByLabel(i > 9 ? 'Previous month' : 'Next month').click();
  await win.getByTestId('calendar-month').filter({ hasText: 'October 2026' }).waitFor({ timeout: 4000 });
  const day2 = cal.locator('[data-day="2026-10-02"]');
  await day2.getByText('October rent').waitFor({ timeout: 4000 });
  await day2.getByText(eur('+2.100')).first().waitFor({ timeout: 4000 });
  // Several movements on a day: the day's totals come from the backend.
  await day2.getByText(eur(`${M}650`)).waitFor({ timeout: 4000 });
  await day2.click();
  const details = win.getByTestId('calendar-day');
  await details.getByText('02.10.2026').waitFor({ timeout: 4000 });
  await details.getByText(eur(`${M}650,00`)).first().waitFor({ timeout: 4000 });
  await shot('47-transactions-calendar');
  await win.getByLabel('Close day').click();
  await win.getByRole('radio', { name: 'Table' }).click();
  await win.locator('table').first().waitFor({ timeout: 4000 });
});

await check('add, edit and delete straight from the calendar and the table', async () => {
  // Calendar: the "+" on a day opens the form with that date already filled in.
  await win.getByRole('radio', { name: 'Calendar' }).click();
  const cal = win.getByTestId('transactions-calendar');
  const day7 = cal.locator('[data-day="2026-10-07"]');
  await day7.hover();
  await cal.getByLabel('Add on 2026-10-07').click();
  const form = win.getByTestId('calendar-add');
  if ((await form.locator('#day-tx-date').inputValue()) !== '2026-10-07') throw new Error('the day form should start on the day picked');
  await form.locator('#day-tx-amount').fill('15');
  await form.locator('#day-tx-cat').fill('Groceries');
  await form.locator('#day-tx-desc').fill('Calendar coffee');
  await form.getByRole('button', { name: 'Add expense' }).click();
  await day7.getByText('Calendar coffee').waitFor({ timeout: 4000 });
  await shot('48-calendar-add');
  const row = win.getByTestId('calendar-day').locator('tr', { hasText: 'Calendar coffee' });
  await row.getByLabel('Delete', { exact: true }).click();
  await row.getByRole('button', { name: 'Delete', exact: true }).click();
  await day7.getByText('Calendar coffee').waitFor({ state: 'detached', timeout: 4000 });
  await win.getByLabel('Close day').click();

  // Table: "Add transaction" opens the form in a window; then edit and delete the new row (buttons always visible).
  await win.getByRole('radio', { name: 'Table' }).click();
  await addTx({ date: '2026-10-08', amount: '4,50', cat: 'Groceries', desc: 'Modal snack' });
  const listRow = win.locator('tr', { hasText: 'Modal snack' });
  await listRow.getByText(eur(`${M}4,50`)).waitFor({ timeout: 4000 });
  if (!(await listRow.getByLabel('Edit', { exact: true }).isVisible())) throw new Error('edit should be visible without hovering');
  await listRow.getByLabel('Edit', { exact: true }).click();
  const edit = win.getByRole('dialog').filter({ hasText: 'Edit transaction' });
  await edit.locator('#edit-tx-amount').fill('9');
  await edit.getByRole('button', { name: 'Save changes' }).click();
  await listRow.getByText(eur(`${M}9,00`)).waitFor({ timeout: 4000 });
  await listRow.getByLabel('Delete', { exact: true }).click();
  await listRow.getByRole('button', { name: 'Delete', exact: true }).click();
  await txCount(5);
});

await check('category rename keeps history', async () => {
  await withCategories(async (dlg) => {
    const item = dlg.locator('li', { hasText: 'Groceries' }).first();
    await item.hover();
    await item.getByLabel('Rename Groceries').click();
    await dlg.locator('li input').fill('Food');
    await dlg.locator('li input').press('Enter');
    await dlg.getByLabel('Rename Food').waitFor({ state: 'attached', timeout: 4000 });
  });
  await win.locator('td span', { hasText: 'Food' }).first().waitFor({ timeout: 4000 });
});

await check('calculator on every tab', async () => {
  for (const name of ['Overview', 'Forecast', 'Transactions']) {
    await tab(name);
    await win.getByLabel('Open calculator').waitFor({ timeout: 4000 });
  }
  await win.getByLabel('Open calculator').click();
  const calc = win.getByRole('dialog', { name: 'Calculator' });
  await calc.getByLabel('Calculation').fill('12,5 + 7.5 × 2');
  await calc.locator('output', { hasText: '= 27.5' }).waitFor({ timeout: 4000 }); // worked out by the backend
  await calc.getByRole('button', { name: 'Clear' }).click();
  for (const key of ['2', '0', '0', '×', '1', '5', '%']) await calc.getByRole('button', { name: key, exact: true }).click();
  await calc.locator('output', { hasText: '= 30' }).waitFor({ timeout: 4000 });
  await calc.getByRole('button', { name: 'Equals' }).click();
  if ((await calc.getByLabel('Calculation').inputValue()) !== '30') throw new Error('= should carry the result on');
  await calc.getByLabel('Calculation').fill('12 +');
  await calc.getByLabel('Calculation').press('Enter');
  await calc.getByText('The calculation is not finished').waitFor({ timeout: 4000 });
  // It keeps what you typed while you change tab.
  await tab('Overview');
  if ((await calc.getByLabel('Calculation').inputValue()) !== '12 +') throw new Error('the calculator should survive a tab change');
  await shot('46-calculator');
  await calc.getByLabel('Close calculator').click();
  await win.getByLabel('Open calculator').waitFor({ timeout: 4000 });
  await tab('Transactions');
});

await check('joint profile starts empty and keeps its own data', async () => {
  await profile('joint');
  await win.fill('#setup-year', '2026');
  await win.fill('#setup-balance', '500');
  await win.click('button:has-text("Get started")');
  // The tab you were on stays open after switching profile.
  await win.getByText('No transactions match').waitFor({ timeout: 4000 });
  await win.waitForTimeout(500);
  // Joint Transactions shows one month: the one picked on the Overview.
  await overviewMonth(9);
  await tab('Transactions');
  await addTx({ date: '2026-10-05', amount: '120', cat: 'Groceries', desc: 'Weekly shop together' });
  await expectText('Weekly shop together');
  await shot('43-joint-transactions');
  const joint = JSON.parse(fs.readFileSync(path.join(dataDir, 'joint', 'data.json'), 'utf8'));
  if (joint.years['2026'].transactions.length !== 1) throw new Error('joint file wrong');
  await profile('personal');
  await txAll();
  await txCount(5);
  if ((await win.getByText('Weekly shop together').count()) > 0) throw new Error('joint data shown in personal');
});

const saved = JSON.parse(fs.readFileSync(path.join(dataDir, 'data.json'), 'utf8'));
await check('data file has what was entered', async () => {
  const n = saved.years['2026'].transactions.length;
  if (n !== 5) throw new Error(`expected 5 transactions on disk, got ${n}`);
  if (saved.goals.length !== 1) throw new Error('goal missing');
  if (saved.goals[0].contributions.length !== 2) throw new Error('distribution contribution missing');
  if (saved.investments.length !== 1) throw new Error('investment plan missing');
  const payment = saved.years['2026'].transactions.find((t) => t.cat === 'Land');
  if (!payment || payment.installments !== 1) throw new Error('investment payment should count as 1 cuota');
  if (saved.schema_version !== 10) throw new Error(`schema version should be 10, is ${saved.schema_version}`);
});

// -- Phase 1: emergency fund, income calendar, bank import, payee rules ------------

const FIXTURE = path.resolve('../backend/tests/fixtures/2026-11-13-sparkasse-camt-v8-synthetic.csv');

await check('emergency fund tile asks for a goal, then shows months covered', async () => {
  await overviewMonth(9);
  await expectText('Choose which savings goal is your emergency fund');
  await tab('Transactions');
  await withCategories(async (dlg) => {
    await dlg.getByLabel('Rent is essential').click();
    await dlg.locator('button[aria-label="Rent is essential"][aria-pressed="true"]').waitFor({ timeout: 4000 });
  });
  await tab('Forecast');
  await win.getByLabel('Goal actions').first().click();
  await win.click('button:has-text("Edit goal")');
  await win.check('#goal-emergency');
  await win.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
  await expectText('Emergency fund');
  await tab('Overview');
  // October: €200 saved in the goal by month end; essential costs = October's rent €650 -> 0,3 months.
  await win.getByTestId('emergency-months').filter({ hasText: '0,3' }).waitFor({ timeout: 4000 });
  await expectText('Too thin');
  await shot('50-overview-emergency');
});

await check('income calendar: settings, payslip, scenario lines', async () => {
  await tab('Forecast');
  await expectText('Projected balance');
  await win.click('button:has-text("Set up the income calendar")');
  await win.fill('#inc-rate', '20');
  await win.getByLabel('Lecture period 1 first day').fill('2026-10-01');
  await win.getByLabel('Lecture period 1 last day').fill('2027-01-15');
  await win.fill('#inc-health', 'Insurance');
  await win.getByLabel('Scenario 1 end date').fill('2027-08-31');
  await win.getByLabel('Scenario 1 health insurance').fill('250');
  await win.getByLabel('Scenario 2 end date').fill('2028-01-31');
  await win.getByLabel('Scenario 2 health insurance').fill('250');
  await win.click('button:has-text("Save settings")');
  // Net pay follows the German tax rules straight away — no payslip needed.
  await expectText('The forecast uses these figures.');
  await win.locator('th', { hasText: 'Income tax' }).first().waitFor({ timeout: 4000 });
  await win.fill('#slip-month', '2026-10');
  await win.fill('#slip-gross', '1000');
  await win.fill('#slip-net', '900');
  await win.click('button:has-text("Add payslip")');
  await expectText('The forecast uses these figures.');
  await expectText('In 12 months · Best case');
  await expectText('In 12 months · Worst case');
  await expectText('student job ends 31.08.2027');
  await shot('51-forecast-income-calendar');
});

await check('import a CSV: preview, then save', async () => {
  await txAll();
  await win.click('main button:has-text("Import CSV")');
  await win.setInputFiles('input[aria-label="Statement file"]', FIXTURE);
  await win.getByTestId('import-summary').filter({ hasText: '7 new, 2 skipped' }).waitFor({ timeout: 4000 });
  await expectText('Still pending at the bank');
  await expectText('Bäckerei Süß'); // the bank's old encoding is read correctly
  // Give both coffees a category, so the app can suggest a rule afterwards.
  await win.getByLabel('Category for row 5').fill('Eating out');
  await win.getByLabel('Category for row 6').fill('Eating out');
  await shot('52-import-preview');
  await win.click('button:has-text("Save 7 rows")');
  await expectText('Saved 7 transactions');
  await win.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).last().click();
  await txCount(12);
});

await check('payee rules: suggestion, manual rule, re-import finds everything', async () => {
  const rules = win.getByTestId('payee-rules');
  await rules.getByText('the category Eating out 2 times', { exact: false }).first().waitFor({ timeout: 4000 });
  await win.click('button:has-text("Add rule “baeckerei suess” → Eating out")');
  await rules.locator('li', { hasText: 'baeckerei suess' }).waitFor({ timeout: 4000 });
  await rules.getByRole('button', { name: '+ Add rule' }).click();
  await rules.getByLabel('Rule text').fill('Muster Markt');
  await rules.getByLabel('Rule category').fill('Food');
  await rules.getByLabel('Add rule', { exact: true }).click();
  await rules.locator('li', { hasText: 'Muster Markt' }).waitFor({ timeout: 4000 });
  await win.click('main button:has-text("Import CSV")');
  await win.setInputFiles('input[aria-label="Statement file"]', FIXTURE);
  await win.getByTestId('import-summary').filter({ hasText: '0 new, 9 skipped' }).waitFor({ timeout: 4000 });
  await shot('53-import-again');
  await win.getByRole('dialog').getByLabel('Close', { exact: true }).first().click();
});

await check('phase 1 data on disk, joint untouched', async () => {
  const now = JSON.parse(fs.readFileSync(path.join(dataDir, 'data.json'), 'utf8'));
  if (now.years['2026'].transactions.length !== 12) throw new Error('expected 12 transactions after import');
  if (!now.income_plan || now.income_plan.payslips.length !== 1 || now.income_plan.scenarios.length !== 2) throw new Error('income plan missing');
  if (now.payee_rules.length !== 2) throw new Error('expected 2 payee rules');
  if (!now.goals[0].emergency_fund) throw new Error('emergency fund flag missing');
  const rent = now.years['2026'].categories.expense.find((c) => c.name === 'Rent');
  if (!rent?.essential) throw new Error('Rent should be essential');
  const joint = JSON.parse(fs.readFileSync(path.join(dataDir, 'joint', 'data.json'), 'utf8'));
  if (joint.income_plan || joint.payee_rules.length) throw new Error('joint should have no income plan or rules');
});

// -- Phase 2: one-off, sinking funds, recurring bills, Joint links -----------------

const isoIn = (days) => { const d = new Date(); d.setDate(d.getDate() + days); return d.toISOString().slice(0, 10); };

await check('one-off tag on a transaction', async () => {
  await txAll();
  await addTx({ date: '2026-11-05', amount: '900', cat: 'Shopping', desc: 'Wedding suit', oneOff: true });
  await win.locator('tr', { hasText: 'Wedding suit' }).getByText('one-off').waitFor({ timeout: 4000 });
});

await check('sinking fund: create, add money, pay from fund', async () => {
  await tab('Forecast');
  await win.click('button:has-text("New goal")');
  await win.getByRole('radio', { name: 'Sinking fund (repeats)' }).click();
  await win.fill('#goal-name', 'Semester fee');
  await win.fill('#goal-target', '220');
  await win.fill('#goal-date', '2027-02-01');
  await win.selectOption('#goal-repeat', '6');
  await win.click('button:has-text("Create goal")');
  const card = win.locator('article', { hasText: 'Semester fee' });
  await card.getByText('Every 6 months').waitFor({ timeout: 4000 });
  await card.getByText(eur('36,67')).waitFor({ timeout: 4000 }); // 220 / 6, from the backend
  await card.getByRole('button', { name: 'Add money' }).click();
  await card.getByLabel('Contribution amount').fill('300');
  await card.getByRole('button', { name: 'Add to Semester fee' }).click();
  await card.getByText('The next bill is covered').waitFor({ timeout: 4000 });
  await card.getByRole('button', { name: 'Pay from fund' }).click();
  await win.click('button:has-text("Pay the bill")');
  await card.getByText('next bill 01.08.2027').waitFor({ timeout: 4000 });
  await card.getByText(eur('80,00')).first().waitFor({ timeout: 4000 }); // 300 − 220 left in the fund
  await shot('60-sinking-fund');
  await overviewMonth(10);
  await expectText(`${eur('220')} of bills paid from sinking funds`);
});

await check('recurring bill shows in the Overview calendar', async () => {
  await tab('Transactions');
  const bills = win.getByTestId('recurring-bills');
  await bills.getByRole('button', { name: '+ Add bill' }).click();
  await bills.getByLabel('Bill name').fill('Phone');
  await bills.getByLabel('Bill amount').fill('22');
  await bills.getByLabel('Bill category').fill('Phone & Internet');
  await bills.getByLabel('Next due date').fill(isoIn(5));
  await bills.getByLabel('Add bill', { exact: true }).click();
  await bills.locator('li', { hasText: 'Phone' }).getByText('monthly').waitFor({ timeout: 4000 });
  await tab('Overview');
  const cal = win.getByTestId('bills-goals-calendar');
  const due = isoIn(5);
  if (!(await cal.locator(`[data-day="${due}"]`).count())) await cal.getByLabel('Next month').click();
  const cell = cal.locator(`[data-day="${due}"]`);
  await cell.getByText('Phone').waitFor({ timeout: 4000 });
  await cell.click();
  const details = win.getByTestId('calendar-day');
  await details.getByText('Phone').first().waitFor({ timeout: 4000 });
  await details.getByText('Money ready').first().waitFor({ timeout: 4000 });
  await details.getByText(eur('22,00')).first().waitFor({ timeout: 4000 });
  // Goals sit beside the calendar, with their progress.
  await cal.getByText('Savings goals').waitFor({ timeout: 4000 });
  await cal.getByText('Laptop').first().waitFor({ timeout: 4000 });
  await shot('61-overview-calendar');
});

await check('transfer to Joint writes a linked record in both profiles', async () => {
  await txAll();
  await win.click('main button:has-text("Transfer to Joint")');
  await win.fill('#transfer-amount', '300');
  await win.fill('#transfer-date', '2026-11-02');
  await win.getByRole('dialog').getByRole('button', { name: 'Transfer', exact: true }).click();
  await win.locator('tr', { hasText: 'Transfer to Joint' }).getByText('linked').waitFor({ timeout: 4000 });
  await profile('joint');
  await overviewMonth(10);
  await tab('Transactions');
  const list = win.getByTestId('joint-tx-list');
  await list.getByText(eur('+300,00')).waitFor({ timeout: 4000 });
  await list.getByText('From Josu').first().waitFor({ timeout: 4000 });
  if ((await win.getByRole('button', { name: 'Transfer to Joint' }).count()) > 0) throw new Error('no transfer button in Joint');
});

await check('joint: fair share and settle-up', async () => {
  await overviewMonth(10);
  await expectText('Between us');
  // Plain English for Isa, and every field has a visible label with the real names.
  await expectText('Until both incomes are filled in, we split 50/50.');
  await win.getByLabel('Josu’s net income per month').fill('2000');
  await win.getByLabel('Isa’s net income per month').fill('3000');
  await win.click('button:has-text("Save names and incomes")');
  await win.getByTestId('fair-share').getByText('40%').waitFor({ timeout: 4000 });
  await win.getByTestId('fair-share').getByText('60%').waitFor({ timeout: 4000 });
  await win.getByLabel('Shared cost description').fill('Groceries for both');
  await win.getByLabel('Shared cost amount').fill('100');
  await win.locator('section', { hasText: 'Settle up' }).getByRole('button', { name: 'Add', exact: true }).click();
  // Josu paid 100 by fair share -> Isa owes her 60%.
  const settle = win.getByTestId('settle-up');
  await settle.filter({ hasText: 'Isa owes Josu' }).waitFor({ timeout: 4000 });
  await settle.getByText(eur('60,00')).waitFor({ timeout: 4000 });
  await shot('62-joint-overview');
  await profile('personal');
});

await check('joint: four tabs, simple overview and forecast, Personal pays its part', async () => {
  // Joint has no Net worth or Settings tab: opening Joint from Settings lands on its Overview.
  await tab('Settings');
  await profile('joint');
  await expectText('Our shared money');
  const tabs = await win.locator('nav[aria-label="Main"] button').allInnerTexts();
  if (tabs.join(',') !== 'Overview,Transactions,Calendar,Forecast') throw new Error(`joint tabs: ${tabs.join(',')}`);
  // November: the €300 transferred from Personal is Josu's money in ("Who pays what").
  await win.selectOption('header select[aria-label="Month"]', '10');
  await win.getByTestId('joint-tiles').waitFor({ timeout: 4000 });
  await win.getByText(`So far we put in ${eur('300,00')}`).first().waitFor({ timeout: 4000 });
  await win.getByTestId('who-pays').getByText('Isa', { exact: true }).waitFor({ timeout: 4000 });
  await shot('63-joint-overview-simple');
  // The plan: rent €650 in December -> Josu pays 40% (€260), Isa 60% (€390), both rows locked.
  await tab('Forecast');
  await expectText('What we pay each month');
  if ((await win.getByRole('radio', { name: 'Share of income' }).count()) > 0) throw new Error('Joint plan shows the % view');
  const rent = win.getByLabel('Rent budget Dec');
  await rent.fill('650');
  await rent.press('Tab');
  await win.waitForFunction(() => document.querySelector('[aria-label="From Josu budget Dec"]')?.value === '260', null, { timeout: 4000 });
  const partnerDec = win.getByLabel('From Isa budget Dec');
  if ((await partnerDec.inputValue()) !== '390') throw new Error(`From Isa Dec is ${await partnerDec.inputValue()}`);
  if (!(await partnerDec.getAttribute('title'))?.includes('Fills itself from our plan')) throw new Error('From Isa Dec does not say it follows the plan');
  await win.getByTestId('joint-bill-tiles').waitFor({ timeout: 4000 });
  await shot('64-joint-forecast');
  const billCard = win.locator('section', { has: win.locator('h2', { hasText: 'What we pay each month' }) }).first();
  await billCard.screenshot({ path: path.join(outDir, '65-joint-bill-card.png') });
  // Personal: "Transfer to Joint" fills itself with Josu's part (it can be typed over by hand).
  await profile('personal');
  await tab('Forecast');
  const half = win.getByLabel('Transfer to Joint budget Dec');
  await half.waitFor({ timeout: 4000 });
  if ((await half.inputValue()) !== '260') throw new Error(`Transfer to Joint Dec is ${await half.inputValue()}`);
  if ((await half.getAttribute('data-typed')) !== null) throw new Error('Transfer to Joint Dec looks typed by hand');
  if (!(await half.getAttribute('title'))?.includes('Fills itself from the Joint plan')) throw new Error('no Joint hint');
});

await check('phase 2 data on disk', async () => {
  const p = JSON.parse(fs.readFileSync(path.join(dataDir, 'data.json'), 'utf8'));
  const j = JSON.parse(fs.readFileSync(path.join(dataDir, 'joint', 'data.json'), 'utf8'));
  if (p.schema_version !== 10) throw new Error('schema version should be 10');
  const txs = p.years['2026'].transactions;
  if (txs.length !== 15) throw new Error(`expected 15 personal transactions, got ${txs.length}`);
  if (!txs.find((t) => t.desc === 'Wedding suit')?.one_off) throw new Error('one-off flag missing');
  const fund = p.goals.find((g) => g.name === 'Semester fee');
  if (fund?.goal_type !== 'sinking' || fund.target_date !== '2027-08-01') throw new Error('sinking fund wrong');
  if (!fund.contributions.some((c) => c.withdrawal && c.amount === 220)) throw new Error('withdrawal missing');
  if (p.recurring_bills.length !== 1) throw new Error('recurring bill missing');
  const out = txs.find((t) => t.link_id);
  const into = j.years['2026'].transactions.find((t) => t.link_id);
  if (!out || !into || out.link_id !== into.link_id) throw new Error('transfer halves not linked');
  if (j.shared_expenses.length !== 1 || j.fair_share.income_b !== 3000) throw new Error('joint settle-up data missing');
  if (p.shared_expenses.length) throw new Error('personal should have no shared costs');
});

// -- Phase 3: tax export, net worth with EUR/PYG, encrypted backups, export --------

await check('tax export with commute estimate', async () => {
  await txAll();
  await withCategories(async (dlg) => {
    await dlg.getByLabel('Shopping is tax-relevant').click();
    await dlg.locator('button[aria-label="Shopping is tax-relevant"][aria-pressed="true"]').waitFor({ timeout: 4000 });
  });
  await win.click('main button:has-text("Tax export")');
  const totals = win.getByTestId('tax-totals');
  await totals.locator('tr', { hasText: 'Shopping' }).getByText(eur('900,00')).waitFor({ timeout: 4000 });
  await win.fill('#tax-days', '100');
  await win.fill('#tax-km', '10');
  await win.click('button:has-text("Save commute")');
  await totals.getByText(eur('380,00')).first().waitFor({ timeout: 4000 }); // 100 × 10 km × €0.38
  await win.click('button:has-text("Save as CSV…")');
  await expectText('Saved as 2026-tax-export.csv');
  const csv = fs.readFileSync(path.join(saveDir, '2026-tax-export.csv'), 'utf8');
  if (!csv.includes('Shopping;Wedding suit;900,00')) throw new Error('tax CSV content wrong');
  await shot('70-tax-export');
  await win.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).last().click();
});

await check('land payment records the guaraníes received', async () => {
  await addTx({ date: '2026-11-06', amount: '330', cat: 'Land', foreign: '2.170.000', desc: 'Cuota November' });
  await expectText('Cuota November');
});

await check('net worth: rate, land as asset and debt, account, exchange cost', async () => {
  await tab('Net worth');
  await expectText('not counted — enter an exchange rate');
  await win.getByLabel('Guaraníes per euro').fill('7000');
  await win.getByLabel('Rate date').fill('2026-11-01');
  await win.getByLabel('Save rate').click();
  await win.getByTestId('current-rate').getByText(gs('7.000')).waitFor({ timeout: 4000 });
  const items = win.getByTestId('net-worth-items');
  // 130 cuotas × 2,170,000 Gs / 7,000 = €40,300; 113 still to pay = €35,030.
  await items.locator('tr', { hasText: 'Plot of land' }).getByText(eur('40.300,00')).first().waitFor({ timeout: 4000 });
  await items.getByText(eur(`${M}35.030,00`)).first().waitFor({ timeout: 4000 });
  // One total row: the net worth.
  if ((await items.locator('tfoot tr').count()) !== 1) throw new Error('expected a single total row');
  await items.locator('tfoot tr', { hasText: 'Net worth' }).waitFor({ timeout: 4000 });
  await win.getByLabel('Account name').fill('Tagesgeld');
  await win.getByLabel('Add account').click();
  await win.getByLabel('Value of Tagesgeld', { exact: true }).fill('4500');
  await win.click('button:has-text("Update")');
  await items.locator('tr', { hasText: 'Tagesgeld' }).getByText(eur('4.500,00')).waitFor({ timeout: 4000 });
  // €330 bought 2,170,000 Gs; at 7,000 Gs/€ that is €310 -> the transfer cost €20.
  await win.getByTestId('exchange-costs').getByText('(6,06%)').waitFor({ timeout: 4000 });
  await expectText(`transfers cost you ${eur('20,00')}`);
  await shot('71-net-worth');
});

await check('encrypted backup: make, verify, wrong password, restore', async () => {
  await tab('Settings');
  await win.fill('#backup-password', 'e2e backup password');
  await win.fill('#backup-repeat', 'e2e backup password');
  await win.click('button:has-text("Make backup and save…")');
  await expectText(`Saved as ${path.basename(backupFile)}`);
  const raw = fs.readFileSync(backupFile, 'utf8');
  if (raw.includes('Tagesgeld') || raw.includes('Wedding suit')) throw new Error('backup is not encrypted');
  await win.click('button:has-text("Choose backup file…")');
  await win.getByTestId('backup-file').filter({ hasText: '.pcbackup' }).waitFor({ timeout: 4000 });
  await win.fill('#verify-password', 'not the password');
  await win.click('button:has-text("Verify backup")');
  await expectText('Wrong password');
  await win.fill('#verify-password', 'e2e backup password');
  await win.click('button:has-text("Verify backup")');
  await win.getByTestId('verify-result').getByText('All totals match').waitFor({ timeout: 8000 });
  await shot('72-backup-verified');
  // Change the data, then restore the backup: the account comes back.
  // Deleting an account asks first (Keep / Delete).
  await tab('Net worth');
  await win.getByLabel('Delete account Tagesgeld').click();
  const ask = win.getByRole('group', { name: /^Delete Tagesgeld/ });
  await ask.getByRole('button', { name: 'Keep' }).click();
  await win.getByTestId('net-worth-items').locator('tr', { hasText: 'Tagesgeld' }).waitFor({ timeout: 4000 });
  await win.getByLabel('Delete account Tagesgeld').click();
  await ask.getByRole('button', { name: 'Delete', exact: true }).click();
  await expectText('No other accounts yet');
  await tab('Settings');
  await win.click('button:has-text("Choose backup file…")');
  await win.fill('#verify-password', 'e2e backup password');
  await win.click('button:has-text("Verify backup")');
  await win.getByTestId('verify-result').getByText('All totals match').waitFor({ timeout: 8000 });
  await win.click('button:has-text("Restore this backup…")');
  await win.click('button:has-text("Yes, restore")');
  await expectText('Restored. Safety copies');
  await tab('Net worth');
  await win.getByTestId('net-worth-items').locator('tr', { hasText: 'Tagesgeld' }).waitFor({ timeout: 4000 });
  if (!fs.readdirSync(dataDir).some((f) => f.startsWith('data-before-restore-'))) throw new Error('no safety copy');
});

await check('export everything', async () => {
  await tab('Settings');
  await win.click('button:has-text("All transactions (CSV)…")');
  await expectText(`Saved as ${todayIso}-personal-transactions.csv`);
  if (!fs.readFileSync(path.join(saveDir, `${todayIso}-personal-transactions.csv`), 'utf8').includes('Wedding suit')) throw new Error('CSV export wrong');
  await win.click('button:has-text("The whole data file (JSON)…")');
  await expectText(`Saved as ${todayIso}-personal-data.json`);
});

await check('phase 3 data on disk', async () => {
  const p = JSON.parse(fs.readFileSync(path.join(dataDir, 'data.json'), 'utf8'));
  if (p.schema_version !== 10) throw new Error('schema version should be 10');
  const y = p.years['2026'];
  if (!y.categories.expense.find((c) => c.name === 'Shopping')?.tax_relevant) throw new Error('tax flag missing');
  if (y.commute_days !== 100 || y.commute_km !== 10) throw new Error('commute missing');
  const cuota = y.transactions.find((t) => t.desc === 'Cuota November');
  if (cuota?.foreign_amount !== 2170000 || cuota.foreign_currency !== 'PYG') throw new Error('foreign amount missing');
  if (p.exchange_rates.length !== 1 || p.accounts.length !== 1) throw new Error('rate or account missing after restore');
});

await check('budget vs real: one bar per variable budget, with a table view', async () => {
  await overviewMonth(9);
  const card = win.locator('section', { has: win.locator('h2', { hasText: /^Budget vs real$/ }) });
  const bars = card.getByTestId('budget-chart');
  await bars.getByTestId('budget-row-Food').waitFor({ timeout: 4000 });
  await bars.getByTestId('budget-row-Food').getByText(`of ${eur('300')}`).waitFor({ timeout: 4000 });
  await card.getByRole('radio', { name: 'Table' }).click();
  await card.locator('th', { hasText: 'Left' }).waitFor({ timeout: 4000 });
  await card.getByRole('radio', { name: 'Chart' }).click();
  await card.getByTestId('budget-chart').waitFor({ timeout: 4000 });
});

await check('budget plan shows fixed and variable subtotals', async () => {
  await tab('Forecast');
  // October: Food (variable) is budgeted at €300; no fixed cost is budgeted. Year total of variable: €300.
  const variable = win.getByTestId('subtotal-variable-costs');
  await variable.getByText('All variable costs').waitFor({ timeout: 4000 });
  if (!(await variable.innerText()).includes('300')) throw new Error('variable subtotal missing 300');
  await win.getByTestId('subtotal-fixed-costs').getByText('All fixed costs').waitFor({ timeout: 4000 });
});

await check('budget plan: planned split by %, % typing, investments section', async () => {
  await tab('Forecast');
  const panel = win.getByTestId('allocation-panel');
  await panel.getByText('Planned split of income').waitFor({ timeout: 4000 });
  // November: 10% of whatever salary is planned (it may come from the income calendar).
  const salaryNov = Number(await win.getByLabel('Salary budget Nov').inputValue());
  const expected = String(Math.round(salaryNov * 10) / 100);
  const cell = win.getByLabel('Food budget Nov');
  await cell.fill('10%');
  await cell.press('Tab');
  await win.waitForFunction((v) => document.querySelector('[aria-label="Food budget Nov"]')?.value === v, expected, { timeout: 4000 });
  await panel.getByRole('radio', { name: 'Nov' }).click();
  await panel.getByTestId('allocation-savings').waitFor({ timeout: 4000 });
  const share = await win.getByTestId('share-variable').innerText();
  if (!share.includes('%')) throw new Error('share row shows no %');
  // January has no planned income: a % cannot be turned into euros.
  const jan = win.getByLabel('Food budget Jan');
  await jan.fill('5%');
  await jan.press('Tab');
  await expectText('no planned income');
  // The investments section is always there, with its own subtotal.
  await win.locator('td', { hasText: 'Investments' }).first().waitFor({ timeout: 4000 });
  await win.getByTestId('subtotal-investments').getByText('All investments').waitFor({ timeout: 4000 });
  await shot('60-forecast-planned-split');
});

await check('linked % budgets, salary from the calendar, tax breakdown', async () => {
  await tab('Forecast');
  // The calendar shows tax, pension and the share taken off; the payslip is checked against the rules.
  await win.getByTestId('tax-refund').waitFor({ timeout: 4000 });
  await win.getByTestId('payslip-check-1').waitFor({ timeout: 4000 });
  // Salary months not recorded yet fill themselves from the income calendar (and can be typed over).
  if (!(await win.getByLabel('Salary budget Dec').getAttribute('title'))?.includes('Fills itself from the income calendar')) throw new Error('Salary Dec does not follow the calendar');
  // "Share of income" view: one % for the whole row.
  await win.getByRole('radio', { name: 'Share of income', exact: true }).click();
  const year = win.getByLabel('Food % for all open months');
  await year.fill('10');
  await year.press('Tab');
  await win.waitForFunction(() => document.querySelector('[aria-label="Food budget Dec"]')?.value === '10', null, { timeout: 4000 });
  await win.getByLabel('Food % for all open months').scrollIntoViewIfNeeded();
  await win.screenshot({ path: path.join(outDir, '62-percent-view.png') });
  // Back to euros: the cell is linked and holds 10 % of December's expected net pay.
  await win.getByRole('radio', { name: 'Euros', exact: true }).click();
  const dec = win.getByLabel('Food budget Dec');
  await win.waitForFunction(() => document.querySelector('[aria-label="Food budget Dec"]')?.dataset.linked === 'true', null, { timeout: 4000 });
  const title = await dec.getAttribute('title');
  if (!title || !title.includes('follows 10%')) throw new Error(`no link in title: ${title}`);
  if (!(Number(await dec.inputValue()) > 0)) throw new Error('linked budget is empty');
  await shot('61-forecast-linked-percent');
});

await check('variable costs by % of income: slider panel', async () => {
  await tab('Forecast');
  const panel = win.getByTestId('share-panel');
  await panel.getByText('Variable costs by % of income').waitFor({ timeout: 4000 });
  // Only variable costs get a slider; fixed costs are a reference line.
  if (await panel.getByLabel('Rent % of income').count()) throw new Error('fixed cost has a slider');
  // Eating out: drag the slider (keyboard) to 4 %.
  const slider = panel.getByLabel('Eating out % of income');
  await slider.focus();
  for (let i = 0; i < 8; i++) await slider.press('ArrowRight');
  await win.waitForFunction(() => document.querySelector('[aria-label="Eating out % exact"]')?.value === '4', null, { timeout: 4000 });
  // Saved for the coming months: the row now shows a euro range, and December's cell is linked to 4 %.
  await panel.getByTestId('share-row-Eating out').getByText('€').first().waitFor({ timeout: 4000 });
  await win.waitForFunction(() => document.querySelector('[aria-label="Eating out budget Dec"]')?.dataset.linked === 'true', null, { timeout: 4000 });
  const title = await win.getByLabel('Eating out budget Dec').getAttribute('title');
  if (!title?.includes('follows 4%')) throw new Error(`not linked: ${title}`);
  // Tabbing past an untouched slider changes nothing.
  await panel.getByLabel('Transport % of income').focus();
  await win.keyboard.press('Tab');
  await win.waitForTimeout(400);
  if ((await win.getByLabel('Transport budget Dec').getAttribute('data-linked')) === 'true') throw new Error('untouched slider saved');
  await panel.getByTestId('share-panel-totals').getByText('Left for savings').waitFor({ timeout: 4000 });
  // In the euro view a linked cell is marked with €, never %.
  const unit = await win.getByLabel('Eating out budget Dec').evaluate((el) => el.parentElement.querySelector('span')?.textContent);
  if (unit !== '€') throw new Error(`linked cell in € view shows "${unit}"`);
  await win.getByLabel('Eating out budget Dec').scrollIntoViewIfNeeded();
  await win.screenshot({ path: path.join(outDir, '64-euro-view-linked.png') });
  await panel.scrollIntoViewIfNeeded();
  await win.screenshot({ path: path.join(outDir, '63-variable-share-panel.png') });
});

await check('fold-away sections on Overview and Forecast', async () => {
  const foldAndOpen = async (label, gone) => {
    await win.getByRole('button', { name: `Fold ${label}` }).click();
    await gone().waitFor({ state: 'detached', timeout: 4000 });
    await win.getByRole('button', { name: `Open ${label}` }).waitFor({ timeout: 4000 });
  };
  const reopen = (label) => win.getByRole('button', { name: `Open ${label}` }).click();
  const box = (title) => win.locator('section', { has: win.locator('h2', { hasText: title }) }).first().boundingBox();

  await tab('Overview');
  // Where your income went and Investments sit next to each other.
  const dist = await box(/^Where your income went$/);
  const invest = await box(/^Investments$/);
  if (!dist || !invest || Math.abs(dist.y - invest.y) > 2 || invest.x <= dist.x) throw new Error('income went and investments are not side by side');
  await foldAndOpen('Upcoming bills & savings goals', () => win.getByTestId('bills-goals-calendar'));
  await foldAndOpen('Where your income went', () => win.getByTestId('distribution-bar'));
  await foldAndOpen('Investments', () => win.locator('section', { has: win.locator('h2', { hasText: /^Investments$/ }) }).getByText('Plot of land').first());
  await shot('65-overview-folded');
  await reopen('Upcoming bills & savings goals');
  await reopen('Where your income went');
  await reopen('Investments');
  await win.getByTestId('distribution-bar').waitFor({ timeout: 4000 });
  await win.getByTestId('bills-goals-calendar').waitFor({ timeout: 4000 });

  await tab('Forecast');
  // Savings goals and Investments are stacked in the column beside "Month by month".
  const goals = await box(/^Savings goals$/);
  const inv = await box(/^Investments$/);
  const table = await win.getByTestId('month-by-month').boundingBox();
  if (!inv || !goals || Math.abs(inv.x - goals.x) > 2 || !(goals.y < inv.y)) throw new Error('goals and investments are not stacked');
  if (!table || !(goals.x > table.x + table.width - 2)) throw new Error('goals are not beside "Month by month"');
  await foldAndOpen('Income calendar', () => win.getByTestId('tax-refund'));
  await foldAndOpen('Investments', () => win.getByRole('button', { name: 'New plan' }));
  await foldAndOpen('Savings goals', () => win.getByRole('button', { name: 'New goal' }));
  await shot('66-forecast-folded');
  for (const label of ['Income calendar', 'Investments', 'Savings goals']) await reopen(label);
  await win.getByTestId('tax-refund').waitFor({ timeout: 4000 });
  await shot('67-forecast-stacked');
});

await check('goals bought in the forecast; land budget follows the plan', async () => {
  await tab('Forecast');
  // A one-time goal is bought in the forecast on its date: a flag, a chip in "Month by month", a check on its card.
  // (The Laptop goal became the emergency fund earlier, so it stays in the account.)
  await win.click('button:has-text("New goal")');
  await win.fill('#goal-name', 'Bike');
  await win.fill('#goal-target', '400');
  await win.fill('#goal-date', '2027-03-15');
  if (!(await win.locator('#goal-spend').isChecked())) throw new Error('a one-time goal should be spent by default');
  await win.click('button:has-text("Create goal")');
  await win.getByText('A goal is bought (the money leaves the account)').waitFor({ timeout: 4000 });
  // Two graduation scenarios here, so the free-to-use line is named after the first one (no single tile).
  await win.getByText('— balance minus money set aside for goals', { exact: false }).waitFor({ timeout: 4000 });
  const card = win.locator('[data-testid^="goal-forecast-"]').filter({ hasText: 'March 2027' }).first();
  await card.waitFor({ timeout: 4000 });
  if (!(await card.innerText()).includes('bought in March 2027')) throw new Error('goal card has no forecast check');
  // "Month by month" is always on screen; the goal is a chip in its month.
  await win.getByTestId('month-by-month').getByTestId('goals-bought-2027-03').getByText('Bike').waitFor({ timeout: 4000 });
  await shot('68-forecast-goals');
  const chartCard = win.getByTestId('projected-balance');
  await chartCard.scrollIntoViewIfNeeded();
  await chartCard.screenshot({ path: path.join(outDir, '69-forecast-chart-goals.png') });
  // Switching goal purchases off removes the flags.
  await win.getByLabel('Include goal purchases').uncheck();
  await win.getByText('A goal is bought (the money leaves the account)').waitFor({ state: 'detached', timeout: 4000 });
  await win.getByLabel('Include goal purchases').check();
  await win.getByText('A goal is bought (the money leaves the account)').waitFor({ timeout: 4000 });
  // The land budget fills itself from its plan (one cuota at €340; it can be typed over by hand).
  const dec = win.getByLabel('Land budget Dec');
  if ((await dec.getAttribute('data-typed')) !== null) throw new Error('Land Dec looks typed by hand');
  if ((await dec.inputValue()) !== '340') throw new Error(`Land Dec is ${await dec.inputValue()}`);
  if (!(await dec.getAttribute('title'))?.includes('Fills itself from the investment plan')) throw new Error('no plan hint');
});

await check('calendar tab: test calendar and money dates, Personal and Joint, pay day', async () => {
  await profile('personal');
  await tab('Calendar');
  // Before access: one button asks; the money dates already show (the Phone bill, due in 5 days).
  const banner = win.getByTestId('calendar-access');
  const allowButton = banner.getByRole('button', { name: 'Allow calendar access' });
  await allowButton.waitFor({ timeout: 4000 });
  const next = win.getByTestId('next-14-days');
  await next.getByText('Phone').first().waitFor({ timeout: 4000 });
  await next.getByText('Still to pay').first().waitFor({ timeout: 4000 });
  if (await next.getByText('Lecture: Statistics').count()) throw new Error('events shown before access');
  await shot('70-calendar-ask');
  // "Allow": the test calendar's events appear (lectures every Monday and Wednesday).
  await allowButton.click();
  await banner.waitFor({ state: 'detached', timeout: 6000 });
  await next.getByText('Lecture: Statistics').first().waitFor({ timeout: 4000 });
  const month = win.getByTestId('calendar-tab-month');
  const lectureDays = month.locator('[data-day]', { hasText: 'Lecture: Statistics' });
  await lectureDays.first().click();
  const day = win.getByTestId('calendar-tab-day');
  await day.getByText('10:00–11:30').first().waitFor({ timeout: 4000 });
  await day.getByText('University').first().waitFor({ timeout: 4000 });
  // Clicking the chosen day again keeps its panel open.
  await lectureDays.first().click();
  await win.waitForTimeout(300);
  await day.getByText('10:00–11:30').first().waitFor({ timeout: 4000 });
  await shot('71-calendar-month');
  // Filters: events off hides them in the month, on shows them again.
  const events = win.getByRole('group', { name: 'Show in the calendar' }).getByRole('button', { name: /Events/ });
  await events.click();
  await lectureDays.first().waitFor({ state: 'detached', timeout: 4000 });
  if ((await events.getAttribute('aria-pressed')) !== 'false') throw new Error('Events filter not off');
  await events.click();
  await lectureDays.first().waitFor({ timeout: 4000 });
  // Settings → Apple Calendar: hide University -> its lectures leave the Calendar tab; then show it again.
  await tab('Settings');
  await win.getByTestId('calendar-card').getByRole('heading', { name: 'Apple Calendar' }).waitFor({ timeout: 4000 });
  const settings = win.getByTestId('calendar-settings');
  await settings.getByText('Apple Calendar allowed').waitFor({ timeout: 4000 });
  await settings.getByLabel('University').uncheck();
  await settings.getByText('the same in Personal and Joint').waitFor({ timeout: 4000 });
  await shot('72-settings-calendar');
  await tab('Calendar');
  await next.getByText('Phone').first().waitFor({ timeout: 4000 });
  await next.getByText('Lecture: Statistics').first().waitFor({ state: 'detached', timeout: 4000 });
  await tab('Settings');
  await settings.getByLabel('University').check();
  // iPhone sync: on -> the money dates land in the app's own calendars (titles only, no amounts),
  // which never show as event calendars; "Sync now" then finds nothing to change; "Remove" deletes them.
  const iphone = win.getByTestId('iphone-sync');
  await iphone.getByLabel(/Send them to/).check();
  await iphone.getByTestId('last-sync').getByText('Last synced').waitFor({ timeout: 8000 });
  const fakeCal = () => JSON.parse(fs.readFileSync(path.join(dataDir, 'fake-calendar.json'), 'utf8'));
  const titles = Object.values(fakeCal().entries ?? {}).map((e) => e.title);
  if (!titles.includes('Phone due')) throw new Error(`no "Phone due" in the Centwise calendar: ${titles.join(', ')}`);
  if (titles.some((s) => s.includes('€') || s.includes('22'))) throw new Error(`an amount reached the iPhone calendar: ${titles.join(', ')}`);
  if (await settings.getByLabel('Centwise', { exact: true }).count()) throw new Error('own calendar listed as an event calendar');
  await iphone.getByRole('button', { name: 'Sync now' }).click();
  await iphone.getByText('0 added, 0 changed, 0 removed').waitFor({ timeout: 8000 });
  await shot('74-settings-iphone-sync');
  await iphone.getByRole('button', { name: /Remove the Centwise calendars/ }).click();
  await iphone.getByRole('button', { name: 'Delete them' }).click();
  await iphone.getByTestId('last-sync').waitFor({ state: 'detached', timeout: 6000 });
  if (await iphone.getByLabel(/Send them to/).isChecked()) throw new Error('sync still on after removing the calendars');
  if (Object.keys(fakeCal().own ?? {}).length) throw new Error('the Centwise calendars were not removed');
  // Joint: the same calendars, in plain words for Isa.
  await profile('joint');
  await tab('Calendar');
  await win.getByTestId('joint-calendar-headline').waitFor({ timeout: 4000 });
  await expectText('Our shared account');
  await win.getByTestId('next-14-days').getByText('Lecture: Statistics').first().waitFor({ timeout: 4000 });
  await shot('73-joint-calendar');
  // Pay day: set on the income calendar form, kept when the form opens again.
  await profile('personal');
  await tab('Forecast');
  const income = win.locator('section', { has: win.locator('h2', { hasText: 'Income calendar' }) }).first();
  await income.getByRole('button', { name: 'Settings' }).click();
  if ((await win.locator('#inc-pay-day').inputValue()) !== '-1') throw new Error('pay day should start at the working day before the last');
  await win.selectOption('#inc-pay-day', '15');
  await win.click('button:has-text("Save settings")');
  await win.locator('#inc-pay-day').waitFor({ state: 'detached', timeout: 4000 });
  await income.getByRole('button', { name: 'Settings' }).click();
  if ((await win.locator('#inc-pay-day').inputValue()) !== '15') throw new Error('pay day was not kept');
  await win.selectOption('#inc-pay-day', '-1');
  await win.click('button:has-text("Save settings")');
  await win.locator('#inc-pay-day').waitFor({ state: 'detached', timeout: 4000 });
});

await check('typed budget boxes, typed hours and vacation', async () => {
  await profile('personal');
  await tab('Forecast');
  // A box that fills itself (salary from the income calendar) can be typed over: it keeps the
  // typed value and gets the ↺ button; ↺ hands it back to the calendar.
  const sal = win.getByLabel('Salary budget Dec', { exact: true });
  const auto = await sal.inputValue();
  await sal.fill('1234');
  await sal.press('Tab');
  await win.waitForFunction(() => document.querySelector('[aria-label="Salary budget Dec"]')?.getAttribute('data-typed') === 'true', null, { timeout: 4000 });
  if ((await sal.inputValue()) !== '1234') throw new Error(`typed salary not kept: ${await sal.inputValue()}`);
  await sal.scrollIntoViewIfNeeded();
  await shot('75-budget-typed-box');
  await win.getByLabel('Back to automatic: Salary budget Dec').click();
  await win.waitForFunction((v) => {
    const el = document.querySelector('[aria-label="Salary budget Dec"]');
    return el && el.getAttribute('data-typed') === null && el.value === v;
  }, auto, { timeout: 4000 });
  // Income calendar: type the hours of a month; gross follows; ↺ goes back to the calendar's hours.
  const hours = win.locator('input[aria-label^="Hours worked"]').nth(1);
  const label = await hours.getAttribute('aria-label');
  await hours.fill('50');
  await hours.press('Tab');
  await win.waitForFunction((l) => document.querySelector(`[aria-label="${l}"]`)?.getAttribute('data-typed') === 'true', label, { timeout: 4000 });
  if ((await hours.inputValue()) !== '50') throw new Error('typed hours not kept');
  const month = label.replace('Hours worked ', '');
  await win.getByLabel(`Back to the calendar's hours: ${month}`).click();
  await win.waitForFunction((l) => document.querySelector(`[aria-label="${l}"]`)?.getAttribute('data-typed') === null, label, { timeout: 4000 });
  // Vacation: three days a month ahead show on that month with their pay; then deleted.
  const vac = win.getByTestId('vacations');
  await vac.getByLabel('First day').fill(isoIn(35));
  await vac.getByLabel('Last day').fill(isoIn(37));
  await vac.getByLabel('Note (optional)').fill('Trip');
  await vac.getByRole('button', { name: 'Add vacation' }).click();
  await vac.getByText('Trip').waitFor({ timeout: 4000 });
  const badge = win.locator('[data-testid^="vacation-"]').first();
  await badge.waitFor({ timeout: 4000 });
  if (!/vacation day/.test(await badge.innerText()) || !/€/.test(await badge.innerText())) throw new Error(`vacation badge: ${await badge.innerText()}`);
  await vac.scrollIntoViewIfNeeded();
  await shot('76-income-vacation');
  await vac.getByRole('button', { name: /Delete vacation from/ }).click({ force: true });
  await vac.getByText('Trip').waitFor({ state: 'detached', timeout: 4000 });
});

// -- New UI: attention banner, shortcuts, forecast ranges, net worth history, dark mode ---
// These run last, so the data they add changes no earlier check. The attention banner only
// looks at the month that is running now, so the made-up costs below are dated today.

const thisMonth = now.getMonth();
await check('overview attention banner: the problem and a one-click move', async () => {
  await profile('personal');
  await txAll();
  // A variable cost far over its budget, and another one with plenty of room.
  await addTx({ date: todayIso, amount: '300', cat: 'Hobby', desc: 'Model kit' });
  await addTx({ date: todayIso, amount: '10', cat: 'Gifts', desc: 'Birthday card' });
  await tab('Forecast');
  for (const [cat, amount] of [['Hobby', '100'], ['Gifts', '500']]) {
    const cell = win.getByLabel(`${cat} budget ${MONTHS_SHORT[thisMonth]}`, { exact: true });
    await cell.fill(amount);
    await cell.press('Tab');
  }
  await win.waitForTimeout(500);
  await overviewMonth(thisMonth);
  const banner = win.getByTestId('attention-banner');
  await banner.getByText('Over budget').waitFor({ timeout: 4000 });
  // Hobby: 300 spent of 100 -> 200 over (the sentence and the amounts come from the backend).
  await banner.getByText(`Hobby is ${eur('200')} over its ${eur('100')} budget.`).waitFor({ timeout: 4000 });
  const move = banner.getByTestId('attention-move');
  await move.waitFor({ timeout: 4000 });
  if (!/^Move .+ from .+/.test(await move.innerText())) throw new Error(`move button says "${await move.innerText()}"`);
  await shot('77-overview-attention');
  await move.click();
  await win.getByTestId('undo-toast').getByText(/^Moved .+ of budget from .+ to Hobby\.$/).waitFor({ timeout: 4000 });
  await banner.getByText('Hobby is').waitFor({ state: 'detached', timeout: 4000 });
});

await check('keyboard: ⌘1–6 switch tabs, ⌘K calculator, ⌘N add, ⌘F search, ⌘↵ saves quick entry', async () => {
  await win.locator('main h1').first().click();
  const names = ['Overview', 'Transactions', 'Calendar', 'Forecast', 'Net worth', 'Settings'];
  for (const i of [2, 4, 6, 3, 5, 1]) {
    await win.keyboard.press(`Meta+${i}`);
    await win.waitForFunction((n) => document.querySelector('nav[aria-label="Main"] button[aria-current="page"]')?.textContent === n, names[i - 1], { timeout: 4000 });
    await win.locator('main h1').first().waitFor({ timeout: 4000 });
  }
  if ((await current()) !== 'Overview') throw new Error('⌘1 should open Overview');
  // ⌘K opens and closes the calculator.
  await win.keyboard.press('Meta+k');
  await win.getByRole('dialog', { name: 'Calculator' }).waitFor({ timeout: 4000 });
  await win.keyboard.press('Meta+k');
  await win.getByRole('dialog', { name: 'Calculator' }).waitFor({ state: 'detached', timeout: 4000 });
  // ⌘N from Overview opens Transactions with the add window.
  await win.keyboard.press('Meta+n');
  const add = win.getByRole('dialog', { name: 'Add a transaction' });
  await add.waitFor({ timeout: 4000 });
  if ((await current()) !== 'Transactions') throw new Error('⌘N should open Transactions');
  await win.keyboard.press('Escape');
  await add.waitFor({ state: 'detached', timeout: 4000 });
  // ⌘F jumps to the search box.
  await win.locator('main h1').first().click();
  await win.keyboard.press('Meta+f');
  await win.waitForFunction(() => document.activeElement?.getAttribute('type') === 'search', null, { timeout: 4000 });
  // ⌘↵ in quick entry saves the rows.
  const qe = win.getByTestId('quick-entry');
  await qe.getByLabel('Description, row 1').fill('Shortcut snack');
  await qe.getByLabel('Category, row 1').fill('Gifts');
  await qe.getByLabel('Amount in euros, row 1').fill('5');
  await qe.getByLabel('Amount in euros, row 1').press('Meta+Enter');
  await qe.getByText('✓ Saved 1 transaction').waitFor({ timeout: 4000 });
  // Settings lists only shortcuts that work.
  await win.keyboard.press('Meta+6');
  const list = await win.getByTestId('shortcuts').innerText();
  for (const k of ['⌘1–6', '⌘N', '⌘K', '⌘F', '⌘↵', 'Esc']) if (!list.includes(k)) throw new Error(`Settings does not list ${k}`);
});

await check('forecast ranges sentence with 6+ months of history', async () => {
  await tab('Forecast');
  const ranges = win.getByTestId('forecast-ranges');
  await ranges.getByText('In 8 of 10 likely futures you stay above').waitFor({ timeout: 4000 });
  const m = (await ranges.innerText()).match(/Based on (\d+) months of history/);
  if (!m || Number(m[1]) < 6) throw new Error(`expected 6+ months of history: ${await ranges.innerText()}`);
  // The chart draws the two ranges and names them.
  await win.getByTestId('projected-balance').getByLabel('Chart legend').getByText('80% range').waitFor({ timeout: 4000 });
  await win.getByTestId('projected-balance').scrollIntoViewIfNeeded();
  await win.getByTestId('projected-balance').screenshot({ path: path.join(outDir, '78-forecast-ranges.png') });
  // The Overview's 6-month card says the same kind of sentence.
  await tab('Overview');
  await win.getByTestId('overview-forecast').getByText('likely futures', { exact: false }).first().waitFor({ timeout: 4000 });
  await win.getByTestId('overview-forecast').screenshot({ path: path.join(outDir, '79-overview-forecast-card.png') });
});

await check('net worth history chart', async () => {
  await tab('Net worth');
  const chart = win.getByTestId('net-worth-chart');
  await chart.locator('svg').first().waitFor({ timeout: 4000 });
  const summary = await chart.getAttribute('aria-label');
  if (!summary) throw new Error('the chart has no summary for screen readers');
  // Positive net worth: each bar stacks net worth (solid) + owed (light cap), so the solid part matches the number on top.
  if ((await chart.getAttribute('data-mode')) !== 'stacked') throw new Error(`net worth chart mode is ${await chart.getAttribute('data-mode')}`);
  const legend = win.getByTestId('net-worth-history').getByLabel('Chart legend');
  await legend.getByText('Owed', { exact: true }).waitFor({ timeout: 4000 });
  await legend.getByText('Estimated month').waitFor({ timeout: 4000 });
  await expectText('Held in guaraníes');
  await win.getByTestId('net-worth-history').screenshot({ path: path.join(outDir, '80-net-worth-history.png') });
});

/** Waits until every chart on screen has drawn its picture (they measure their box first). */
const chartsDrawn = async () => {
  await win.waitForFunction(() => [...document.querySelectorAll('.recharts-responsive-container')]
    .every((box) => box.clientWidth > 0 && box.querySelector('svg.recharts-surface')), null, { timeout: 6000 });
  await win.waitForTimeout(1500);
};
const DARK_TABS = ['Overview', 'Transactions', 'Calendar', 'Forecast', 'Net worth', 'Settings'];
await check('appearance: Dark is saved and stays after a reload; screenshots of every tab', async () => {
  await tab('Settings');
  const card = win.getByTestId('appearance');
  await card.getByRole('button', { name: 'Dark', exact: true }).click();
  await win.waitForFunction(() => document.documentElement.getAttribute('data-theme') === 'dark', null, { timeout: 4000 });
  await card.locator('button[aria-pressed="true"]', { hasText: 'Dark' }).waitFor({ timeout: 4000 });
  // Saved in the app's own preferences (no money data in that file).
  const stateFile = path.join(dataDir, 'app-state.json');
  for (let i = 0; i < 20; i++) {
    if (fs.existsSync(stateFile) && JSON.parse(fs.readFileSync(stateFile, 'utf8')).prefs?.appearance === 'dark') break;
    await win.waitForTimeout(200);
  }
  if (JSON.parse(fs.readFileSync(stateFile, 'utf8')).prefs?.appearance !== 'dark') throw new Error('Dark was not saved');
  await win.reload();
  await win.locator('nav[aria-label="Main"]').waitFor({ timeout: 8000 });
  await win.waitForFunction(() => document.documentElement.getAttribute('data-theme') === 'dark', null, { timeout: 8000 });
  for (const [i, name] of DARK_TABS.entries()) {
    await tab(name);
    await win.locator('main h1').first().waitFor({ timeout: 4000 });
    if (name === 'Overview') await win.selectOption('header select[aria-label="Month"]', String(thisMonth));
    await chartsDrawn();
    await shot(`9${i}-dark-${name.toLowerCase().replace(' ', '-')}`);
  }
  // Back to light.
  await tab('Settings');
  await win.getByTestId('appearance').getByRole('button', { name: 'Light', exact: true }).click();
  await win.waitForFunction(() => document.documentElement.getAttribute('data-theme') === 'light', null, { timeout: 4000 });
});

await check('joint screens in light', async () => {
  await profile('joint');
  await expectText('Our shared money');
  await win.selectOption('header select[aria-label="Month"]', '10');
  for (const name of ['Overview', 'Transactions', 'Calendar', 'Forecast']) {
    await tab(name);
    await win.locator('main h1').first().waitFor({ timeout: 4000 });
    await chartsDrawn();
    await shot(`85-joint-light-${name.toLowerCase()}`);
  }
  await profile('personal');
});

await check('header fits in narrow windows (Personal and Joint, Overview has the most controls)', async () => {
  // Every control must sit inside the window: nothing cut off at the right edge.
  const fits = () => win.evaluate(() => {
    const header = document.querySelector('header');
    const out = [...header.querySelectorAll('nav button, select')]
      .filter((el) => el.getBoundingClientRect().right > window.innerWidth + 0.5)
      .map((el) => el.getAttribute('aria-label') || el.textContent.trim());
    return { out, overflow: header.scrollWidth > header.clientWidth + 0.5 };
  });
  for (const width of [1100, 1224, 1360]) {
    for (const id of ['personal', 'joint']) {
      await win.setViewportSize({ width, height: 900 });
      await profile(id);
      await tab('Overview');
      await win.locator('header select[aria-label="Month"]').waitFor({ timeout: 4000 });
      const r = await fits();
      if (r.out.length || r.overflow) throw new Error(`${id} at ${width}px: cut off ${JSON.stringify(r.out)}, overflow ${r.overflow}`);
      if (width === 1100) await win.screenshot({ path: path.join(outDir, `86-header-${id}-1100.png`), clip: { x: 0, y: 0, width, height: 80 } });
    }
  }
  await profile('personal');
  await win.setViewportSize({ width: 1360, height: 900 });
});

await check('category dots: every budget row, same colour on every screen, Joint list and Categories window', async () => {
  const colour = (cls) => (cls ?? '').split(' ').find((c) => /^bg-(chart-\d|invest|positive)$/.test(c));
  await profile('personal');
  await win.selectOption('header select[aria-label="Month"]', '10');
  await tab('Forecast');
  await win.getByLabel('Food budget Jan').waitFor({ timeout: 4000 });
  // Every category row in the budget plan has its dot: cash in green, investments violet.
  const rows = await win.evaluate(() => [...document.querySelectorAll('tr')]
    .filter((tr) => tr.querySelector('input[aria-label$=" budget Jan"]'))
    .map((tr) => ({ name: tr.querySelector('td')?.innerText.trim(), dot: tr.querySelector('[data-testid="category-dot"]')?.className ?? '' })));
  if (rows.length < 3) throw new Error(`only ${rows.length} budget rows`);
  const missing = rows.filter((r) => !r.dot).map((r) => r.name);
  if (missing.length) throw new Error(`budget rows without a dot: ${missing.join(', ')}`);
  if (!rows.some((r) => r.dot.includes('bg-positive'))) throw new Error('no green cash-in dot in the budget plan');
  if (!rows.some((r) => r.dot.includes('bg-invest'))) throw new Error('no violet investment dot in the budget plan');
  if (rows.some((r) => r.dot.includes('bg-chart-8'))) throw new Error('a category got the grey "no category" dot');
  await win.locator('tr', { has: win.getByLabel('Food budget Jan') }).screenshot({ path: path.join(outDir, '87-budget-row-dot.png') });
  // The same category has the same colour in the budget plan, the Transactions list and the Overview.
  // Cash-in rows are always green, so compare the cash-out colours (a name can be both cash in and cash out).
  const plan = new Map(rows.filter((r) => !r.dot.includes('bg-positive')).map((r) => [r.name, colour(r.dot)]));
  const chipColours = () => win.evaluate(() => [...document.querySelectorAll('main span.chip')]
    .map((s) => ({ name: s.innerText.trim(), cls: s.querySelector('span[aria-hidden], [data-testid="category-dot"]')?.className ?? '' }))
    .filter((c) => c.cls));
  for (const name of ['Transactions', 'Overview']) {
    await tab(name);
    await win.locator('main span.chip').first().waitFor({ timeout: 4000 });
    const shared = (await chipColours()).filter((c) => plan.has(c.name) && !c.cls.includes('bg-positive'));
    if (name === 'Transactions' && !shared.length) throw new Error('no category in both the budget plan and the Transactions list');
    const wrong = shared.filter((c) => colour(c.cls) !== plan.get(c.name));
    if (wrong.length) throw new Error(`${name}: ${wrong.map((c) => `${c.name} ${colour(c.cls)} vs plan ${plan.get(c.name)}`).join(', ')}`);
  }
  // Categories window: a dot in front of every name.
  await tab('Transactions');
  await withCategories(async (dlg) => {
    const items = dlg.locator('ul > li');
    const n = await items.count();
    const dots = await dlg.locator('ul > li [data-testid="category-dot"]').count();
    if (!n || dots !== n) throw new Error(`categories window: ${dots} dots for ${n} categories`);
  });
  // Joint: "What we pay each month" has a dot per line.
  await profile('joint');
  await tab('Forecast');
  const card = win.getByTestId('joint-what-we-pay');
  await card.locator('li').first().waitFor({ timeout: 4000 });
  const lines = await card.locator('ul > li').count();
  const jointDots = await card.locator('[data-testid="category-dot"]').count();
  if (!jointDots) throw new Error('no dots in "What we pay each month"');
  await card.screenshot({ path: path.join(outDir, '88-joint-what-we-pay-dots.png') });
  if (jointDots < lines - 1) throw new Error(`"What we pay each month": ${jointDots} dots for ${lines} lines`);
  await profile('personal');
});

fs.writeFileSync(path.join(outDir, 'console.txt'), errors.join('\n') || '(clean)');
console.log(`\n${failures} failure(s); console: ${errors.length ? errors.join(' | ') : 'clean'}`);
await app.close();
process.exit(failures ? 1 : 0);
