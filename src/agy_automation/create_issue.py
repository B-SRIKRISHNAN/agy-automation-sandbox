"""Create issue facade for agy-automation.

Re-exports issue creation services from agy_automation.core.create_issue for backward compatibility.
"""

import sys
from .core import create_issue as _create_issue
from .core.create_issue import *  # noqa: F401, F403

sys.modules[__name__] = _create_issue
