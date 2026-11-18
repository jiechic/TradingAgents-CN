#!/usr/bin/env python3
"""Compatibility entry point for the release metadata consistency check."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.release_version import validate

if __name__ == '__main__':
    try:
        print('Version metadata consistent:', validate())
    except (ValueError, KeyError, StopIteration) as exc:
        raise SystemExit(str(exc))
