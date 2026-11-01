"""Push facade for agy-automation.

Re-exports push changes functionality from agy_automation.core.push for backward compatibility.
"""

import sys
from .core import push as _push
from .core.push import *  # noqa: F401, F403

sys.modules[__name__] = _push
