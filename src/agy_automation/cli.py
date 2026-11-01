"""CLI facade for agy-automation.

Re-exports CLI parsing and prompt functions from agy_automation.cli for backward compatibility.
"""

import sys
from . import cli as _cli_pkg
from .cli import *  # noqa: F401, F403

sys.modules[__name__] = _cli_pkg
