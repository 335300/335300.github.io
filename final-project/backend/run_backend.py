"""Entry point for the frozen (PyInstaller) backend.

PyInstaller runs its entry script as a top-level module, so the relative imports
inside ``app/__main__.py`` would have no parent package. Importing the package
absolutely from here keeps ``app`` a real package. In development the backend is
started with ``python -m app``; this file is only used by the build.
"""

import multiprocessing
import sys

from app.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
