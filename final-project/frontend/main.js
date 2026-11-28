'use strict';

/**
 * Electron main process.
 *
 * Owns the Python backend: picks a free loopback port, generates a one-shot
 * bearer token, spawns the backend, waits for /health, and makes sure the child
 * dies with the app.
 *
 * The page never talks to the backend itself. It asks this process over IPC
 * (see preload.js) and this process makes the HTTP call. So the page needs no
 * network access at all, never learns the port or token, and its CSP can keep
 * connect-src locked down.
 */

const { app, BrowserWindow, dialog, ipcMain, nativeTheme, shell } = require('electron');
const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');

const DEV = process.argv.includes('--dev');
const DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL || 'http://127.0.0.1:5173';
const PROJECT_ROOT = path.join(__dirname, '..');
const BACKEND_DIR = path.join(PROJECT_ROOT, 'backend');
const VENV_PYTHON = path.join(BACKEND_DIR, '.venv', 'bin', 'python');

const TOKEN = crypto.randomBytes(32).toString('hex');
// The frozen backend needs a few seconds on first launch; readiness is decided
// by polling /health, so a generous limit costs nothing when it starts fast.
const STARTUP_TIMEOUT_MS = 45000;

// Electron's own browser cache would default to ~/Library/Application Support/<name> —
// possibly the same folder as our data. Keep it apart, and apart from the course app.
// Tests and development (a throwaway CENTWISE_DATA_DIR) get their own browser storage
// inside that folder, so they never share remembered choices (folded cards, Calendar |
// List) with the installed app — in either direction.
app.setPath(
  'userData',
  process.env.CENTWISE_DATA_DIR
    ? path.join(process.env.CENTWISE_DATA_DIR, 'electron-profile')
    : path.join(app.getPath('cache'), 'Centwise Final Project'),
);

let mainWindow = null;
let backend = null;
let backendPort = null;
let shuttingDown = false;

/** Dev: the project's virtualenv. Packaged: the PyInstaller binary inside the .app. */
function backendCommand() {
  if (app.isPackaged) {
    const executable = path.join(process.resourcesPath, 'backend', 'centwise-final-project-backend');
    return { command: executable, args: [], cwd: path.dirname(executable), packaged: true };
  }
  return { command: VENV_PYTHON, args: ['-m', 'app'], cwd: BACKEND_DIR, packaged: false };
}

/** Ask the OS for an unused port by binding to :0 and reading it back. */
function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForBackend(port) {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  let lastError = null;
  while (Date.now() < deadline) {
    if (backend && backend.exitCode !== null) {
      throw new Error(`Backend exited during startup (code ${backend.exitCode})`);
    }
    try {
      const response = await fetch(`http://127.0.0.1:${port}/health`);
      if (response.ok) return await response.json();
      lastError = new Error(`Health check returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await sleep(150);
  }
  throw lastError || new Error('Backend did not become ready in time');
}

async function startBackend() {
  const { command, args, cwd, packaged } = backendCommand();
  if (!fs.existsSync(command)) {
    throw new Error(
      packaged
        ? `The bundled backend is missing from this app (expected at ${command}).\n\nRebuild it with ./build-app.sh.`
        : `Python environment missing at ${command}\n\nRun ./setup.sh from the project root to create it.`
    );
  }

  backendPort = await findFreePort();
  backend = spawn(command, [...args, '--port', String(backendPort)], {
    cwd,
    env: { ...process.env, CENTWISE_TOKEN: TOKEN, PYTHONUNBUFFERED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  backend.stdout.on('data', (chunk) => process.stdout.write(`[backend] ${chunk}`));
  backend.stderr.on('data', (chunk) => process.stderr.write(`[backend] ${chunk}`));
  backend.on('exit', (code, signal) => {
    backend = null;
    if (shuttingDown) return;
    dialog.showErrorBox(
      'Backend stopped',
      `The Centwise Final Project backend stopped unexpectedly (code ${code}, signal ${signal}).\n\n` +
        'The app will now close. Your saved data is untouched.'
    );
    app.quit();
  });
  return waitForBackend(backendPort);
}

function stopBackend() {
  if (!backend) return;
  shuttingDown = true;
  const child = backend;
  backend = null;
  child.kill('SIGTERM');
  // Escalate if uvicorn is wedged; the app must not leave orphans behind.
  setTimeout(() => {
    if (child.exitCode === null) child.kill('SIGKILL');
  }, 2000);
}

/** Only our own page may use the API bridge. */
function isTrustedSender(frame) {
  if (!frame || !mainWindow || frame !== mainWindow.webContents.mainFrame) return false;
  const url = frame.url || '';
  return DEV ? url.startsWith(DEV_SERVER_URL) : url.startsWith('file://');
}

const ALLOWED_METHODS = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE']);

ipcMain.handle('api:request', async (event, { method, endpoint, body }) => {
  if (!isTrustedSender(event.senderFrame)) {
    return { ok: false, status: 403, data: { detail: 'Forbidden' } };
  }
  if (!ALLOWED_METHODS.has(method) || typeof endpoint !== 'string' || !endpoint.startsWith('/api/')) {
    return { ok: false, status: 400, data: { detail: 'Bad request' } };
  }
  try {
    const response = await fetch(`http://127.0.0.1:${backendPort}${endpoint}`, {
      method,
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { detail: text };
      }
    }
    return { ok: response.ok, status: response.status, data };
  } catch (error) {
    return { ok: false, status: 0, data: { detail: `Backend unreachable: ${error.message}` } };
  }
});

// -- Files: only through the normal macOS Save and Open windows ------------------
//
// The page cannot touch the filesystem. It hands a finished file (made by the
// backend) to "file:save", and the user picks where it goes; "file:open" returns
// only the one file the user picked. For the automated UI check only, two
// environment variables replace the windows with a fixed folder / file.
const FILE_MAX_BYTES = 60 * 1024 * 1024;
const E2E_SAVE_DIR = process.env.CENTWISE_E2E_SAVE_DIR;
const E2E_OPEN_FILE = process.env.CENTWISE_E2E_OPEN_FILE;

ipcMain.handle('file:save', async (event, { filename, content_base64 }) => {
  if (!isTrustedSender(event.senderFrame)) return { saved: false, error: 'Forbidden' };
  if (typeof filename !== 'string' || typeof content_base64 !== 'string') return { saved: false, error: 'Bad request' };
  const content = Buffer.from(content_base64, 'base64');
  if (content.length > FILE_MAX_BYTES) return { saved: false, error: 'File too big' };
  const safeName = path.basename(filename).replace(/[^\w.\- ]/g, '_') || 'export';
  let target;
  if (E2E_SAVE_DIR) {
    target = path.join(E2E_SAVE_DIR, safeName);
  } else {
    const result = await dialog.showSaveDialog(mainWindow, { defaultPath: path.join(app.getPath('documents'), safeName) });
    if (result.canceled || !result.filePath) return { saved: false };
    target = result.filePath;
  }
  await fs.promises.writeFile(target, content);
  return { saved: true, name: path.basename(target) };
});

ipcMain.handle('file:open', async (event, { extensions } = {}) => {
  if (!isTrustedSender(event.senderFrame)) return null;
  let source = E2E_OPEN_FILE;
  if (!source) {
    const filters = Array.isArray(extensions) && extensions.length
      ? [{ name: 'Backup', extensions: extensions.filter((e) => typeof e === 'string') }]
      : [];
    const result = await dialog.showOpenDialog(mainWindow, { properties: ['openFile'], filters });
    if (result.canceled || !result.filePaths.length) return null;
    source = result.filePaths[0];
  }
  const stat = await fs.promises.stat(source);
  if (stat.size > FILE_MAX_BYTES) return { error: 'File too big' };
  const content = await fs.promises.readFile(source);
  return { name: path.basename(source), content_base64: content.toString('base64') };
});

// Window background behind the page (seen while loading and at the edges when
// resizing). Matches --c-bg in src/index.css for light and dark, and follows the
// Mac setting. The page's own Light/Dark choice (Settings) only changes the page.
const WINDOW_BG = { light: '#F7F8FA', dark: '#111827' };
const windowBackground = () => (nativeTheme.shouldUseDarkColors ? WINDOW_BG.dark : WINDOW_BG.light);

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: 'Centwise Final Project',
    backgroundColor: windowBackground(),
    titleBarStyle: 'hiddenInset',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());
  if (DEV) {
    mainWindow.loadURL(DEV_SERVER_URL);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'));
  }

  // External links open in the real browser; the app window never navigates away.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) shell.openExternal(url);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!(DEV && url.startsWith(DEV_SERVER_URL))) event.preventDefault();
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  try {
    await startBackend();
  } catch (error) {
    dialog.showErrorBox('Could not start Centwise Final Project', String(error.message || error));
    app.quit();
    return;
  }
  nativeTheme.on('updated', () => {
    if (mainWindow) mainWindow.setBackgroundColor(windowBackground());
  });
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // On macOS the app stays alive after its window closes, and reopening from
  // the dock must find the backend still running.
  if (process.platform !== 'darwin') {
    stopBackend();
    app.quit();
  }
});

app.on('before-quit', stopBackend);
process.on('exit', stopBackend);
