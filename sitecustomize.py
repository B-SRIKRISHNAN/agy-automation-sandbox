"""Automatic src/ directory resolution for python -m invocations from repo root."""

import sys
from pathlib import Path

_repo_src = Path(__file__).resolve().parent / "src"
if _repo_src.is_dir() and str(_repo_src) not in sys.path:
    sys.path.insert(0, str(_repo_src))
