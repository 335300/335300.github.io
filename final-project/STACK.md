# Centwise stack: a blueprint for building a similar app

Give this whole file to another LLM as a brief. It describes how Centwise (and Personal
Centwise) is built: architecture, frontend, backend, storage, the local AI assistant, opening
links in the user's own browser, packaging and testing. It is written as instructions, so the
receiving LLM can reuse the same stack for a different app.

Centwise itself ships for **macOS**. The same stack also works for a **Windows** app:
sections 1–11 describe the shared design (with the macOS details), and **section 12 lists
everything that changes for Windows**, with code. When building for Windows, apply section 12
everywhere it overrides earlier sections.

---

## 1. What kind of app this is

- A **local desktop app** for macOS (Apple Silicon) or Windows (x64), see section 12. It is
  not a website and has no server in the cloud. Everything runs on the user's computer, data
  included.
- **Electron** provides the window. A **React** page draws the UI. A **Python (FastAPI)**
  backend holds all the logic and data. Electron starts the backend when the app opens and
  stops it when the app quits.
- Optional **AI assistant** ("Advisor"): a chat panel that answers questions about the user's
  data using a **local model run by Ollama**. No cloud AI, and no data leaves the Mac.
- External links open in the **user's default browser** (Safari, Chrome…), never inside the
  app window.

```
┌──────────────────────── Electron app (.app bundle) ─────────────────────────┐
│                                                                              │
│  React page (renderer, sandboxed)        Electron main process (Node)        │
│  ─────────────────────────────           ───────────────────────────         │
│  UI, charts, forms                       • starts/stops the Python backend   │
│  window.api.get/post/…  ──── IPC ───▶    • holds the port + secret token     │
│  (no network access, strict CSP)         • makes every HTTP call             │
│                                          • opens external links in the       │
│                                            default browser (shell.openExternal)
│                                                    │ HTTP, 127.0.0.1 only    │
│                                                    ▼                         │
│                                Python backend (FastAPI + uvicorn)            │
│                                • API routers (thin)                          │
│                                • services/ = pure, tested calculations       │
│                                • storage = JSON files, atomic writes, backups│
│                                • agent/ = AI Advisor ──▶ Ollama 127.0.0.1:11434
└──────────────────────────────────────────────────────────────────────────────┘
     Data: macOS ~/Library/Application Support/<App Name>/   Windows %APPDATA%\<App Name>\
```

---

## 2. Tech stack at a glance

| Layer | Choice | Version used |
| --- | --- | --- |
| Desktop shell | Electron | 33.x |
| Packaging | electron-builder (macOS: target `dir`, arm64; Windows: `nsis` installer, x64; unsigned) | 26.x |
| UI framework | React + TypeScript | React 18.3, TS 5.6 |
| Bundler / dev server | Vite + @vitejs/plugin-react | Vite 6.x |
| Styling | Tailwind CSS (+ PostCSS, autoprefixer), tokens in CSS variables | Tailwind 3.4 |
| Charts | Recharts | 2.15 |
| Icons | lucide-react | 1.x |
| Server state | TanStack Query (React Query) | 5.x |
| UI state | Zustand (small store: active tab, selected year/month) | 5.x |
| Dev tooling | concurrently + wait-on (runs Vite and Electron together) | — |
| UI tests | Playwright driving Electron (`_electron.launch`) | 1.x |
| Backend language | Python | 3.11–3.13 (3.12 used) |
| Web framework | FastAPI + uvicorn[standard] | FastAPI ≥0.115, uvicorn ≥0.32 |
| Validation / models | Pydantic v2 | ≥2.9 |
| Backend tests | pytest + httpx (FastAPI TestClient) | pytest ≥8 |
| Backend freezing | PyInstaller (onedir) | ≥6 |
| Storage | One JSON file per profile; no database | — |
| Local AI (optional) | Ollama + small instruct model (default `qwen3:4b-instruct`) | — |
| Language | English everywhere (UI, code, docs) | — |

**Not used, on purpose:** SQLite or any other database, any cloud service, CORS, remote
fonts or CDNs, Node integration in the page, an LLM API key.

---

## 3. Frontend

### 3.1 Layout
```
frontend/
  main.js          Electron main process: backend supervisor, IPC API proxy, link handling
  preload.js       the only bridge into the page (exposes window.api)
  index.html       Vite entry
  vite.config.js   Vite config + build-time CSP injection
  tailwind.config.js, postcss.config.cjs, tsconfig.json
  src/
    main.tsx       React root + QueryClientProvider
    App.tsx        picks the page from the store; first-run setup card
    index.css      Tailwind layers + colour tokens as CSS variables
    api/client.ts  typed wrapper around window.api
    api/queries.ts every TanStack Query hook (reads + mutations)
    lib/           types.ts (backend response shapes), format.ts, store.ts (Zustand), theme.ts
    components/    Header, SetupCard, ui/ (Card, KpiTile, Modal, StatusBadge…), charts/
    pages/         overview/, transactions/, forecast/  (one folder per tab)
  scripts/e2e.mjs  Playwright end-to-end test against the built app
```

### 3.2 Rules for the page
- **The page never computes a business number.** It only displays what the backend returns
  (amounts, percentages, statuses). This keeps one source of truth, and that source is tested.
- **The page never calls `fetch`.** All data goes through `window.api.get/post/put/patch/del`,
  which the preload script exposes and the main process carries out (see 4.2).
- **TanStack Query** handles all server state. Every write calls
  `queryClient.invalidateQueries()` (the data is small and local, so a full refetch is
  instant). Switching profile calls `resetQueries()`.
- **Zustand** holds UI state only: active tab, selected year and month.
- **Styling:** Tailwind with *semantic* colour tokens (`primary`, `positive`, `negative`,
  `warning`, `ink`, `surface`…) defined as RGB channels in CSS variables on `:root` and mapped
  in `tailwind.config.js` with `rgb(var(--c-name) / <alpha-value>)`. Code never uses raw hex
  values or hue names.
- Money uses tabular numerals (`.num { font-variant-numeric: tabular-nums }`).
- **Window chrome:** `titleBarStyle: 'hiddenInset'`. The header has the CSS class
  `drag` (`-webkit-app-region: drag`), and its controls have `no-drag`.

### 3.3 Content-Security-Policy (packaged build only)
A small Vite plugin injects this `<meta>` tag at build time (the dev server needs inline
scripts for hot reload, so dev runs without it):
```
default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline';
img-src 'self' data:; font-src 'self'; connect-src 'none';
base-uri 'none'; form-action 'none'; object-src 'none'
```
`connect-src 'none'` works because the page never makes network requests. `'unsafe-inline'`
for styles is needed only because Recharts writes inline styles. Set Vite `base: './'` so the
built page loads from `file://`.

---

## 4. Electron shell (main.js + preload.js)

### 4.1 Backend supervisor (main process)
1. Ask the OS for a free port (bind a `net` server to `127.0.0.1:0`, read the port, close it).
2. Generate a one-time secret: `crypto.randomBytes(32).toString('hex')`.
3. Spawn the backend with `--port <port>` and env `APP_TOKEN=<secret>` (Centwise calls it
   `CENTWISE_TOKEN`) and `PYTHONUNBUFFERED=1`.
   - **Dev:** `backend/.venv/bin/python -m app`
   - **Packaged:** the PyInstaller binary at `process.resourcesPath/backend/<name>-backend`
4. Poll `GET /health` every 150 ms until it answers (45 s timeout), then open the window.
5. If the backend exits unexpectedly, show an error dialog and quit. On quit, send SIGTERM,
   then SIGKILL after 2 s, so no orphan process is left behind.
6. Move Electron's own cache out of the data folder:
   `app.setPath('userData', path.join(app.getPath('cache'), '<App Name>'))`.
7. macOS: keep the app (and the backend) alive when the window closes, and recreate the
   window on `activate`.

### 4.2 IPC API proxy (why the page has no network access)
- `preload.js` uses `contextBridge.exposeInMainWorld('api', {...})`, which exposes five
  methods. Each one calls `ipcRenderer.invoke('api:request', {method, endpoint, body})`.
- `ipcMain.handle('api:request')` in main.js:
  - accepts the request only if the sender is the app's own main frame (`file://` in
    production, the Vite URL in dev)
  - allows only GET/POST/PUT/PATCH/DELETE, and only endpoints that start with `/api/`
  - calls `http://127.0.0.1:<port><endpoint>` with `Authorization: Bearer <secret>`
  - returns `{ok, status, data}`. The preload script turns errors into `Error` objects and
    flattens FastAPI's validation-error lists into one readable line.
- BrowserWindow `webPreferences`: `contextIsolation: true`, `nodeIntegration: false`,
  `sandbox: true`, `preload: preload.js`.

The result: the page never learns the port or token, cannot reach Node or the filesystem, and
cannot call any other URL.

---

## 5. Opening links in the user's own browser

The app window must never navigate away from the app. Links to the web open in the user's
default browser through Electron's `shell.openExternal`.

**What Centwise does today (main.js):**
```js
// Links with target="_blank" (or window.open) → default browser, https only.
mainWindow.webContents.setWindowOpenHandler(({ url }) => {
  if (url.startsWith('https://')) shell.openExternal(url);
  return { action: 'deny' };           // never open a second Electron window
});
// Any attempt to navigate the app window itself is blocked.
mainWindow.webContents.on('will-navigate', (event, url) => {
  if (!(DEV && url.startsWith(DEV_SERVER_URL))) event.preventDefault();
});
```
In React, write external links as
`<a href="https://example.com" target="_blank" rel="noreferrer">…</a>`.

**Recommended for the new app.** Today a plain link without `target="_blank"` is just
blocked, so it silently does nothing. Make every link work:
```js
const isExternal = (url) => /^https:\/\//i.test(url);   // add mailto: here if wanted

mainWindow.webContents.setWindowOpenHandler(({ url }) => {
  if (isExternal(url)) shell.openExternal(url);
  return { action: 'deny' };
});
mainWindow.webContents.on('will-navigate', (event, url) => {
  if (DEV && url.startsWith(DEV_SERVER_URL)) return;     // Vite hot reload
  event.preventDefault();
  if (isExternal(url)) shell.openExternal(url);
});
```
Optional: expose an explicit bridge method (`window.api.openExternal(url)` → IPC → main
validates `https://` → `shell.openExternal`) for buttons that are not `<a>` tags.

**Links in AI answers:** render the model's text as plain text, or as Markdown with a
sanitiser (for example `react-markdown`, which has no raw HTML by default). Every link it
produces is then an `<a target="_blank">` and goes through the handlers above. Only allow
`https://`, never `file://`, `javascript:` or custom schemes. The CSP needs no change, because
opening a link in another app is not a network request from the page.

---

## 6. Backend (Python / FastAPI)

### 6.1 Layout
```
backend/
  app/
    __main__.py    entry point: argparse --port, prints READY, uvicorn.run(host="127.0.0.1")
    app.py         create_app(): FastAPI app, /health (no auth), routers behind the token check
    config.py      every constant: app name, currency, months, data folder, profiles, thresholds
    models.py      Pydantic v2 schema of the stored document + request bodies (strict, extra=forbid)
    storage.py     Repository (one JSON file) + AppStore (one repository per profile, prefs)
    services/      PURE FUNCTIONS: input = model objects (+ `today`), output = dicts. No I/O, no clock.
    api/           thin routers: validate input, call a service, return the result. No arithmetic.
      deps.py      dependency injection: store/repository, bearer-token check, get_today()
    agent/         (optional) the AI Advisor, see section 7
  tests/           pytest: services, API, storage (+ agent with a scripted fake LLM)
  run_backend.py   PyInstaller entry (imports app.__main__ absolutely)
  <name>.spec      PyInstaller spec (onedir, hidden uvicorn imports)
  pyproject.toml
```

### 6.2 Principles
- **Every number the UI shows is calculated in `services/`** by pure, unit-tested functions.
  Routers and the UI only pass data along.
- **The clock lives at the edge:** `get_today()` is a FastAPI dependency, and services receive
  `today` as an argument. Tests override it to pin the date.
- **Security:** bind to `127.0.0.1` only. No CORS middleware, so a browser tab cannot call the
  backend. `require_token` compares the bearer token with `hmac.compare_digest`. If no token
  is set (tests, local dev), auth is off. `/health` stays open for the readiness check.
- **Config in one file** (`config.py`): currency, starter categories, warning thresholds,
  data folder, profile list.
- API style: REST under `/api/...`. 404 for an unknown year or profile, 409 for conflicts, 422
  for validation. FastAPI's `/docs` page is available when the backend is run on its own.

### 6.3 Storage
- One JSON document per profile, validated by a root Pydantic model with a `schema_version`.
  The app refuses to open a file written by a newer schema.
- **Atomic writes:** write to a temp file in the same folder, `fsync`, then `os.replace`.
- **Backups:** before each save, copy the current file to `backups/data-<timestamp>.json` and
  keep the last 20.
- Nothing is written until the first real change (a first run creates no file).
- An `RLock` per repository. The in-memory model is the source of truth during a session, and
  each save writes the whole file.
- Location: `~/Library/Application Support/<App Name>/` (overridable with an env var such as
  `APP_DATA_DIR` for tests). Extra profiles get sub-folders (for example `joint/`).
  `app-state.json` remembers the last profile and display preferences, and holds no
  financial data.

---

## 7. The local AI assistant (how it works with the LLM)

Built on the course-app branch `agentic_features`. Personal Centwise does **not** include it.

### 7.1 Principles
- **Local only:** the model runs in **Ollama** on the same Mac. The backend talks to it at a
  **hard-coded `http://127.0.0.1:11434`**, so no setting can point it at a remote machine.
  There is no API key and no cloud.
- **The model never calculates.** It only calls **read-only tools**, which wrap the same
  tested services the UI uses, and then explains their results in words.
- **Deterministic number check:** after each answer, the backend pulls every number out of
  the text and checks it against the tool results for that turn. Numbers that don't match are
  flagged, and the UI shows a warning ("numbers not verified").

### 7.2 Pieces (`backend/app/agent/`)
| File | Role |
| --- | --- |
| `llm.py` | `OllamaClient` uses only the **standard library** (`urllib`), so there is no extra dependency and nothing extra to freeze. `chat(model, messages, tools)` → `POST /api/chat` with `stream: false`, `think: false`, `temperature 0.2`, `num_ctx 8192`. If a model rejects `think`, it retries without it. Also `is_up()` (`GET /api/version`) and `list_models()` (`GET /api/tags`). An `LLMClient` Protocol lets tests swap in a scripted fake. |
| `tools.py` | Read-only tools in Ollama/OpenAI function-calling JSON schema: `get_overview(month)`, `get_forecast()`, `get_goals()`, `get_category_history(category)`. Each one calls a service and trims the result so a small model gets short, readable context, with ready-made lists such as `over_budget`. Months are 1–12 for the model and converted to 0–11 internally. Bad arguments come back to the model as an error so it can retry. |
| `prompts.py` | A short system prompt (small models follow short rules best): today's date, open year, currency, category names, active goals, plus rules: always call a tool first; use only numbers from tool results, copied exactly; never do arithmetic; future months are estimates; 2–5 sentences; no investment, tax or legal advice; stay on topic. |
| `loop.py` | `run_turn()`: system prompt + the last 10 chat messages → model. If the model returns `tool_calls`, run each tool, append a `role: tool` message, and call the model again. **At most 4 tool rounds**; the final round offers no tools, so the model has to answer. Strips leaked `<think>…</think>`. Returns `{answer, tools_used, numbers_verified, unverified_numbers, model, latency_ms}`. |
| `verify.py` | The number check described above. It ignores dates ("2026-10-21", "October 21", "3rd") and today's date. |

### 7.3 API and UI
- `GET /api/advisor/status` → `{ollama_up, models[], model, model_installed}` lets the UI
  explain "Open the Ollama app" or "pick an installed model".
- `POST /api/advisor/chat` with `{messages:[{role, content}], year}` → the turn result. The
  turn works on a **deep-copied snapshot** of the data, so a model call that takes several
  seconds never holds the data lock. Errors: 503 if Ollama isn't running or the model isn't
  installed, 502 for a model error.
- The chosen model is saved in the preferences (`app-state.json`) and picked from a dropdown in
  the chat panel.
- The chat panel is a React side panel that uses the same `window.api` bridge (so the CSP
  stays unchanged). It shows "tools used" chips and the unverified-numbers warning, and keeps
  the conversation in UI state (not saved to disk).
- Requirements on the user's Mac: install Ollama, then run `ollama pull qwen3:4b-instruct`
  (≈2.5 GB; fine on an 8 GB M-series Mac). The non-instruct `qwen3:4b` always "thinks" first
  and took 40–120 s per answer.

### 7.4 Tests
`tests/test_agent.py` replaces Ollama with a scripted fake client, then checks the tool loop,
the round limit, think-tag cleanup, the number check and the API errors. No real model is
needed in CI. A separate Playwright script (`scripts/advisor.mjs`) runs against the real local
model by hand.

---

## 8. Packaging and scripts

- `setup.sh`: finds Python 3.11–3.13, creates `backend/.venv`, installs FastAPI, uvicorn,
  Pydantic, pytest and httpx, runs `npm install`, then runs the tests.
- `build-app.sh [--fast] [--install]`:
  1. Draw the icon: `assets/make_icon.py` (Pillow) → 1024 px PNG → `sips` sizes →
     `iconutil` → `icon.icns`
  2. Freeze the backend: `pyinstaller <name>.spec` (onedir, because onefile unpacks on every
     launch and starts slowly; list uvicorn's lazy imports as `hiddenimports`; exclude tkinter,
     numpy and similar)
  3. `npm run build` (`tsc --noEmit && vite build`)
  4. electron-builder (`--mac --arm64`, target `dir`, `identity: null`, `asar: true`). The
     frozen backend is copied in as `extraResources` → `Contents/Resources/backend/`.
     Build in a staging folder under `~/Library/Caches/`, because electron-builder rejects
     paths with characters like apostrophes.
  5. `--install`: quit the running app (`osascript`), kill its backend, copy into
     `/Applications`, and reopen it if it was running.
  - `--fast` skips the icon and the backend freeze (for frontend-only changes).
- package.json `build`: a unique `appId` and `productName` for each app, so two apps can be
  installed side by side, each with its own data folder and backend binary name.

## 9. Testing
- `cd backend && .venv/bin/python -m pytest -q`: services, API (TestClient), storage. Each test
  gets a throwaway data folder (an autouse fixture sets the data-folder env var to `tmp_path`).
- `cd frontend && npm run build && node scripts/e2e.mjs <shots-dir> <throwaway-data-dir>`:
  Playwright launches Electron (set `EXE=` to test the packaged app), clicks through every
  write flow, checks the screen and the JSON on disk, saves screenshots and fails on any
  console error.
- Never point a test at the real data folder.

## 10. Dev commands
```bash
./setup.sh                                        # one-time
cd frontend && npm run dev                        # Vite + Electron with DevTools (no CSP)
cd backend && .venv/bin/python -m app --port 8137 # backend alone, API docs at /docs
./build-app.sh --install                          # build + install the .app
```

---

## 11. Instructions for the LLM building the new app

1. Reuse this architecture exactly: Electron main process as backend supervisor and API
   proxy, sandboxed React page with the `window.api` bridge, FastAPI backend on loopback with
   a one-time token, JSON storage with atomic writes and backups.
2. Put **all domain logic in pure Python services with pytest tests**. The UI and the AI only
   display or explain results.
3. Give the app its own name, `appId`, data folder and backend binary name.
4. Use the **link handling from section 5** (recommended version): `https://` links open in
   the default browser, and the app window never navigates.
5. If the app has an AI assistant: Ollama on `127.0.0.1:11434` only, read-only tools over
   services, short system prompt, at most 4 tool rounds, number check, a fake LLM client in
   tests, and AI-generated links rendered safely and opened via `shell.openExternal`.
6. Keep the strict CSP and `contextIsolation`/`sandbox`, and never enable `nodeIntegration`.
7. Before calling a change done: the backend tests pass, the app was actually launched (e2e
   script), and no real user data is in the project folder.
8. **If the target is Windows, apply section 12.** Write the code so it works on both
   platforms where that costs nothing (data folder, Python path, binary name, title bar), and
   keep only the build scripts platform-specific.

---

## 12. Building it as a Windows application

Most of the stack is cross-platform and stays exactly as described above: Electron, React,
Vite, Tailwind, Recharts, TanStack Query, Zustand, FastAPI, Pydantic, pytest, Playwright, the
IPC bridge, the token check, the CSP, and the storage design. This section lists only what
changes. Target: **Windows 10/11, x64**.

### 12.1 Things that work the same on Windows
- **Opening links:** `shell.openExternal(url)` opens the user's default Windows browser (Edge,
  Chrome, Firefox…). The link handlers from section 5 need no change.
- **Ollama:** there is a Windows installer. It runs in the system tray and listens on the same
  `http://127.0.0.1:11434`, so `llm.py` needs no change. `ollama pull <model>` works the same
  in PowerShell.
- **Loopback + token:** binding uvicorn to `127.0.0.1` and the bearer token work the same.
  Windows Firewall does not prompt for loopback-only servers.
- **Picking a free port** with `net.createServer().listen(0, '127.0.0.1')` works the same.

### 12.2 Data folder
Store data in `%APPDATA%\<App Name>\` (for example `C:\Users\<user>\AppData\Roaming\<App Name>\`).
Choose the folder per platform in `config.py`:

```python
import os, sys
from pathlib import Path

def data_dir() -> Path:
    override = os.environ.get("APP_DATA_DIR")          # tests point this at a temp folder
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME
```
Always use `pathlib` (never hand-built `"/"` strings), so paths work on both systems.

Electron's own browser cache must not land in the data folder either. On Windows, Electron's
default `userData` is `%APPDATA%\<package name>`, which can be the same folder as the data
(folder names ignore case on Windows too). Point it somewhere explicit:
```js
const cacheRoot = process.platform === 'win32'
  ? path.join(process.env.LOCALAPPDATA || app.getPath('temp'), '<App Name>-cache')
  : path.join(app.getPath('cache'), '<App Name>');
app.setPath('userData', cacheRoot);   // call before app 'ready'
```

### 12.3 Starting the backend (main.js)
The dev virtualenv and the frozen binary have different names on Windows:
```js
const WIN = process.platform === 'win32';
const VENV_PYTHON = WIN
  ? path.join(BACKEND_DIR, '.venv', 'Scripts', 'python.exe')
  : path.join(BACKEND_DIR, '.venv', 'bin', 'python');

function backendCommand() {
  if (app.isPackaged) {
    const exe = path.join(process.resourcesPath, 'backend', WIN ? 'app-backend.exe' : 'app-backend');
    return { command: exe, args: [], cwd: path.dirname(exe), packaged: true };
  }
  return { command: VENV_PYTHON, args: ['-m', 'app'], cwd: BACKEND_DIR, packaged: false };
}
```
- Pass `windowsHide: true` to `spawn(...)` so no console window flashes up.
- **Stopping:** on Windows, `child.kill()` always ends the process at once (there is no real
  SIGTERM). That is fine here, because every save is atomic, but kill the whole process tree
  so nothing is left running:
  ```js
  if (WIN) spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { windowsHide: true });
  else child.kill('SIGTERM');
  ```
- Quitting: the existing `window-all-closed` handler already quits on Windows (only macOS
  keeps the app alive with no window open), and `before-quit` stops the backend.
- PyInstaller spec: set `console=False` for the Windows build, so the backend `.exe` opens no
  console window (stdout/stderr still reach Electron through the pipes).

### 12.4 Window and title bar
`titleBarStyle: 'hiddenInset'` and the 84 px left padding for the Mac window buttons are
macOS-only. On Windows use a hidden title bar with the native buttons drawn on the right:
```js
new BrowserWindow({
  ...(WIN
    ? { titleBarStyle: 'hidden', titleBarOverlay: { color: '#FFFFFF', symbolColor: '#1E293B', height: 56 } }
    : { titleBarStyle: 'hiddenInset' }),
  icon: WIN ? path.join(__dirname, 'icon.ico') : undefined,
  // webPreferences unchanged: contextIsolation, sandbox, no nodeIntegration
});
```
In the page, put the padding on the right instead of the left on Windows, leaving room for the
minimise/maximise/close buttons (about 140 px). Expose the platform through the preload
script (`contextBridge.exposeInMainWorld('platform', process.platform)`) and pick the header
class from it. Keep the `drag` / `no-drag` CSS classes: they work on Windows too.

Optional: `Menu.setApplicationMenu(null)` hides the default File/Edit menu bar on Windows.

### 12.5 Storage on Windows
- `os.replace(tmp, path)` is atomic on Windows as well, but it fails with `PermissionError`
  when another process holds the file open for a moment (antivirus, backup tools, an editor).
  Retry a few times:
  ```python
  for attempt in range(5):
      try:
          os.replace(tmp_name, path); break
      except PermissionError:
          if attempt == 4: raise
          time.sleep(0.1 * (attempt + 1))
  ```
- `shutil.copy2` for backups and `os.fsync` work the same.
- Backup file names must not contain `:`. The `%Y%m%d-%H%M%S-%f` timestamp is already safe.
- Always open files with `encoding="utf-8"`: the Windows default encoding is not UTF-8.

### 12.6 Packaging for Windows
**Build on Windows.** PyInstaller cannot build a Windows `.exe` from a Mac, so run the
build on a Windows PC, in a Windows VM, or in CI (GitHub Actions `windows-latest`).

electron-builder config in `package.json` (alongside the existing `mac` block):
```json
"win": {
  "target": [{ "target": "nsis", "arch": ["x64"] }],
  "icon": "../assets/icon.ico"
},
"nsis": {
  "oneClick": false,
  "perMachine": false,
  "allowToChangeInstallationDirectory": true,
  "createDesktopShortcut": true,
  "shortcutName": "<App Name>"
},
"extraResources": [
  { "from": "../backend/dist/app-backend", "to": "backend", "filter": ["**/*"] }
]
```
- Output: `<App Name> Setup <version>.exe` (an installer for the current user, no admin
  rights needed). Use the `portable` target instead for a single `.exe` with no installer.
- **Icon:** Windows needs `icon.ico` (sizes 16, 32, 48, 64, 128, 256). Pillow can write it from
  the same drawing script:
  `img.save("icon.ico", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])`.
- **Unsigned app:** Windows SmartScreen shows "Windows protected your PC". The user clicks
  *More info → Run anyway* once. Removing the warning needs a code-signing certificate
  (`win.certificateFile` / `certificatePassword` in the electron-builder config).
- Data stays in `%APPDATA%\<App Name>\` and survives uninstalling and reinstalling.

### 12.7 Scripts: PowerShell instead of bash
Replace `setup.sh` and `build-app.sh` with `setup.ps1` and `build-app.ps1` (or Node scripts,
which run on both systems). The steps are the same:

`setup.ps1`
```powershell
$ErrorActionPreference = "Stop"
py -3.12 -m venv backend\.venv                      # Python launcher; 3.11-3.13
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\pip.exe install "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9" pytest httpx pyinstaller
Push-Location frontend; npm install; Pop-Location
Push-Location backend; .venv\Scripts\python.exe -m pytest -q; Pop-Location
```

`build-app.ps1`
```powershell
$ErrorActionPreference = "Stop"
# 1. Icon (Pillow) -> assets\icon.ico   (give the icon script an --ico option, see 12.6)
backend\.venv\Scripts\pip.exe install pillow
backend\.venv\Scripts\python.exe assets\make_icon.py assets\icon-1024.png --ico assets\icon.ico
# 2. Freeze the backend -> backend\dist\app-backend\app-backend.exe
Push-Location backend; .venv\Scripts\pyinstaller.exe app.spec --noconfirm; Pop-Location
# 3. Build the page
Push-Location frontend; npm run build
# 4. Package -> frontend\release\<App Name> Setup x.y.z.exe
npx electron-builder --win --x64; Pop-Location
```
To replace a running copy before installing:
`Stop-Process -Name "<App Name>","app-backend" -ErrorAction SilentlyContinue`.

Avoid spaces and special characters in the build output path, as on macOS.

### 12.8 Dev mode on Windows
`npm run dev` works the same (concurrently + wait-on + Vite + Electron). The `dev` script must
not use bash-only syntax. The current `"vite --port 5173 --strictPort"` / `"wait-on
tcp:127.0.0.1:5173 && electron . --dev"` pair already works in `cmd` and PowerShell.

### 12.9 Tests on Windows
- pytest and the Playwright e2e script run the same. For the packaged app, set
  `EXE="C:\Users\<user>\AppData\Local\Programs\<App Name>\<App Name>.exe"`.
- Write path assertions with `pathlib`, and make data-folder tests platform-aware (for
  example, expect `AppData\Roaming\<App Name>` when `sys.platform == "win32"`).
- Run the test suite on both systems in CI (`macos-latest` + `windows-latest`) if the app
  ships for both.

### 12.10 Windows checklist
| Area | macOS | Windows |
| --- | --- | --- |
| Data folder | `~/Library/Application Support/<App>/` | `%APPDATA%\<App>\` |
| Dev Python | `backend/.venv/bin/python` | `backend\.venv\Scripts\python.exe` |
| Frozen backend | `app-backend` | `app-backend.exe` (`console=False`) |
| Stop backend | SIGTERM, then SIGKILL | `taskkill /T /F` |
| Title bar | `hiddenInset`, padding on the left | `hidden` + `titleBarOverlay`, padding on the right |
| Icon | `icon.icns` | `icon.ico` |
| Package | `--mac --arm64`, target `dir` → `.app` | `--win --x64`, target `nsis` → `Setup.exe` |
| Build machine | Mac | Windows (or CI `windows-latest`) |
| Scripts | `setup.sh`, `build-app.sh` | `setup.ps1`, `build-app.ps1` |
| Unsigned warning | Gatekeeper (right-click → Open) | SmartScreen (More info → Run anyway) |
| Links | `shell.openExternal` → default browser | same |
| Local AI | Ollama on `127.0.0.1:11434` | same |
