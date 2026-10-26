#!/usr/bin/env python3
"""Universal CLI bin entry point for agy-automation."""

import sys
from pathlib import Path

# Add toolkit src to sys.path so imports work when invoked from PATH in any working directory
_src_dir = Path(__file__).resolve().parent.parent / "src"
if _src_dir.is_dir() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from agy_automation.orchestrator import main

if __name__ == "__main__":
    sys.exit(main())
