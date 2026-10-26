"""Unit and integration tests for agy-automation."""

import sys
from pathlib import Path

# Ensure src/ is in sys.path for test discovery
_src_dir = Path(__file__).resolve().parent.parent / "src"
if _src_dir.is_dir() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
