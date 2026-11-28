# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the Centwise Final Project backend.

Produces a self-contained `centwise-final-project-backend` folder with its own Python, which
electron-builder copies into the .app. Freezing (rather than shipping .venv)
means the app does not depend on any Python installed on the Mac.

Build with:  .venv/bin/pyinstaller centwise.spec --noconfirm
"""

# Uvicorn resolves these lazily by string, so static analysis cannot see them.
# Missing one gives a binary that builds fine and then dies at startup.
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops", "uvicorn.loops.auto", "uvicorn.loops.asyncio", "uvicorn.loops.uvloop",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl", "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl", "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
    # Apple Calendar: app/apple_calendar.py imports these lazily (inside functions).
    "objc", "Foundation", "AppKit", "EventKit",
]

analysis = Analysis(
    # run_backend.py, not app/__main__.py — see the note in run_backend.py.
    ["run_backend.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "PIL", "numpy", "pandas", "matplotlib", "IPython"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="centwise-final-project-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# onedir, not onefile: onefile unpacks the interpreter on every launch (slow start).
coll = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, upx_exclude=[], name="centwise-final-project-backend")
