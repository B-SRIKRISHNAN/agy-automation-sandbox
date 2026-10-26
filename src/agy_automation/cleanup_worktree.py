"""Script-equivalent module alias for cleanup-worktree."""

import sys
from .cleanup import cleanup_worktree, main

if __name__ == "__main__":
    sys.exit(main())
