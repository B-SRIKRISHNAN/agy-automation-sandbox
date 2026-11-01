"""Executable module entry point for python -m agy_automation."""

import sys
from .cli.main import main

if __name__ == "__main__":
    sys.exit(main())
