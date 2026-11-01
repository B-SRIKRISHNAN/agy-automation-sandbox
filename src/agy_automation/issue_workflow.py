"""Issue workflow facade for agy-automation.

Re-exports issue formulation and creation workflow from agy_automation.core.issue_workflow.
"""

import sys
from .core import issue_workflow as _issue_workflow
from .core.issue_workflow import *  # noqa: F401, F403

sys.modules[__name__] = _issue_workflow
