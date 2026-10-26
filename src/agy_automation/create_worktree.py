"""Script-equivalent module alias for create-worktree."""

import sys
from .worktree import create_worktree, inject_issue_context, main

if __name__ == "__main__":
    sys.exit(main())
