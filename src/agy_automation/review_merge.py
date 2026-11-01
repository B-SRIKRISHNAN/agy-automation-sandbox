"""Review and merge facade for agy-automation.

Re-exports review and merge functionality from agy_automation.core.review_merge for backward compatibility.
"""

import sys
from .core import review_merge as _review_merge
from .core.review_merge import *  # noqa: F401, F403

sys.modules[__name__] = _review_merge
