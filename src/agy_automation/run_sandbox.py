"""Script-equivalent module alias for run-sandbox."""

import sys
from .sandbox import main, run_sandbox

if __name__ == "__main__":
    sys.exit(main())
