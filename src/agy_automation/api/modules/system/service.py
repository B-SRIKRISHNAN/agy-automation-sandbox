"""Service and in-memory TTL caching for Antigravity CLI quota telemetry."""

import json
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from agy_automation.api.modules.system.schemas import (
    QuotaBucket,
    QuotaGroup,
    QuotaResponse,
)
from agy_automation.core.logging import get_logger

logger = get_logger("agy_automation.api.system.service")

# 60-second TTL cache for quota requests
CACHE_TTL_SECONDS = 60.0
_cache_lock = threading.Lock()
_cached_quota: Optional[QuotaResponse] = None
_cached_time: float = 0.0


def parse_quota_data(data: dict) -> QuotaResponse:
    """Parse raw agy CLI JSON payload into strongly typed QuotaResponse."""
    now = datetime.now(timezone.utc)
    cmd = data.get("command") or {}
    cmd_data = cmd.get("data") or {}

    groups = []
    for g in cmd_data.get("groups", []):
        buckets = []
        for b in g.get("buckets", []):
            fraction = float(b.get("remaining_fraction", 0.0))
            percent = max(0, min(100, round(fraction * 100)))
            buckets.append(
                QuotaBucket(
                    id=str(b.get("id", "")),
                    name=str(b.get("name", "")),
                    description=b.get("description"),
                    window=str(b.get("window", "")),
                    remaining_fraction=fraction,
                    remaining_percent=percent,
                    reset_time=b.get("reset_time"),
                )
            )
        groups.append(
            QuotaGroup(
                name=str(g.get("name", "")),
                description=g.get("description"),
                buckets=buckets,
            )
        )

    return QuotaResponse(
        description=cmd_data.get("description"),
        groups=groups,
        cached=False,
        updated_at=now,
    )


def fetch_agy_quota(force_refresh: bool = False) -> QuotaResponse:
    """Fetch current agy model quotas, using a 60-second in-memory cache."""
    global _cached_quota, _cached_time

    now_ts = time.time()
    now_dt = datetime.now(timezone.utc)

    with _cache_lock:
        if not force_refresh and _cached_quota and (now_ts - _cached_time < CACHE_TTL_SECONDS):
            return _cached_quota.model_copy(update={"cached": True})

    agy_bin = shutil.which("agy")
    if not agy_bin:
        logger.warning("agy binary not found in PATH")
        return QuotaResponse(
            groups=[],
            cached=False,
            updated_at=now_dt,
            error="Antigravity CLI (agy) is not installed or not in PATH.",
        )

    try:
        res = subprocess.run(
            [agy_bin, "-p", "/usage", "--output-format", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        if res.returncode != 0:
            err_msg = res.stderr.strip() or f"agy exited with code {res.returncode}"
            logger.warning("agy quota query failed: %s", err_msg)
            return QuotaResponse(
                groups=[],
                cached=False,
                updated_at=now_dt,
                error=f"Failed to query agy quota: {err_msg}",
            )

        raw_json = json.loads(res.stdout)
        quota_resp = parse_quota_data(raw_json)

        with _cache_lock:
            _cached_quota = quota_resp
            _cached_time = time.time()

        return quota_resp

    except subprocess.TimeoutExpired:
        logger.error("Timed out waiting for agy /usage response")
        return QuotaResponse(
            groups=[],
            cached=False,
            updated_at=now_dt,
            error="Timed out waiting for agy quota query.",
        )
    except Exception as exc:
        logger.exception("Unexpected error querying agy quota: %s", exc)
        return QuotaResponse(
            groups=[],
            cached=False,
            updated_at=now_dt,
            error=str(exc),
        )


def reset_quota_cache() -> None:
    """Clear in-memory quota cache (used in unit tests)."""
    global _cached_quota, _cached_time
    with _cache_lock:
        _cached_quota = None
        _cached_time = 0.0
