"""Package path redirect to src/agy_automation for root python -m invocations."""

import sys
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
__path__ = [str(_src / "agy_automation")]
