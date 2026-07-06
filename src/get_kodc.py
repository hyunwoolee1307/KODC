"""Compatibility wrapper for the download CLI.

Prefer:

    pixi run download -- --start-year 1961 --end-year 2025
"""

from __future__ import annotations

import sys

from kodc.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["download", *sys.argv[1:]]))
