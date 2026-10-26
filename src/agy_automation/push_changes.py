"""Script-equivalent module alias for push-changes."""

import sys
from .push import main, push_changes

if __name__ == "__main__":
    sys.exit(main())
