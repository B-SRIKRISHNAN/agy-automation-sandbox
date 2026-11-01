"""Fetch issue facade for agy-automation.

Re-exports issue fetching from agy_automation.core.fetch_issue for backward compatibility.
"""

import sys
from .core import fetch_issue as _fetch_issue
from .core.fetch_issue import *  # noqa: F401, F403

sys.modules[__name__] = _fetch_issue
