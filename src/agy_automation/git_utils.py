"""Git utilities facade for agy-automation.

Re-exports Git utility wrappers from agy_automation.core.git for backward compatibility.
"""

import sys
from .core import git as _git

# Re-export for IDEs and type checkers
from .core.git import *  # noqa: F401, F403

# Alias module in sys.modules so patching 'agy_automation.git_utils.*' works seamlessly
sys.modules[__name__] = _git
