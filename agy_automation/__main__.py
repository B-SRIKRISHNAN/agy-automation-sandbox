"""Executable module entry point for python -m agy_automation."""

import sys
from .orchestrator import main

if __name__ == "__main__":
    sys.exit(main())
