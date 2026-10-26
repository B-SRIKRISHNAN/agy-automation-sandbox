#!/usr/bin/env python3
"""Universal CLI bin entry point for agy-automation."""

import sys
from pathlib import Path

# Add toolkit root to sys.path so imports work when invoked from PATH in any working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agy_automation.orchestrator import main

if __name__ == "__main__":
    sys.exit(main())
