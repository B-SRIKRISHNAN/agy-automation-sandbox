#!/usr/bin/env python3
"""Convenience root entry point for agy-automation."""

import sys
from pathlib import Path

# Ensure src/ is in sys.path
_src_dir = Path(__file__).resolve().parent / "src"
if _src_dir.is_dir() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from agy_automation.orchestrator import main

if __name__ == "__main__":
    sys.exit(main())
