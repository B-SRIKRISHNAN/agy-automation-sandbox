"""Generate issue facade for agy-automation.

Re-exports issue formulation and exploration from agy_automation.core.generate_issue for backward compatibility.
"""

import sys
from .core import generate_issue as _generate_issue
from .core.generate_issue import *  # noqa: F401, F403

sys.modules[__name__] = _generate_issue
