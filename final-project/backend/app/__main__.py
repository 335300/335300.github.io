"""Entry point: ``python -m app --port 8137``.

Started by the Electron main process, which picks a free port, generates a
one-shot token and passes it in the environment (``CENTWISE_TOKEN``).
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys

import uvicorn

from .app import create_app


def main(argv: list[str] | None = None) -> int:
    # Required first in a PyInstaller-frozen binary: otherwise a child process
    # re-runs the whole program instead of the worker entry point.
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(prog="centwise-backend", description="Centwise backend")
    parser.add_argument("--port", type=int, default=8137)
    parser.add_argument("--log-level", default="warning")
    args = parser.parse_args(argv)

    app = create_app()
    print(f"CENTWISE_READY port={args.port}", flush=True)
    # Loopback only — never reachable from another machine.
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":
    sys.exit(main())
