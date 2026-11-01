"""Worktree facade for agy-automation.

Re-exports worktree management functions from agy_automation.core.worktree for backward compatibility.
"""

import sys
from .core import worktree as _worktree
from .core.worktree import *  # noqa: F401, F403

sys.modules[__name__] = _worktree
