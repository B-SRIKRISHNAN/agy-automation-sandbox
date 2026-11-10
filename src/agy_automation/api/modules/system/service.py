"""Service and in-memory TTL caching for Antigravity CLI quota telemetry."""

import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from agy_automation.api.modules.chat.service import chat_manager
from agy_automation.api.modules.projects import repository as projects_repo
from agy_automation.api.modules.runs import repository as runs_repo
from agy_automation.api.modules.runs.schemas import RunStatus
from agy_automation.api.modules.system.schemas import (
    QuotaBucket,
    QuotaGroup,
    QuotaResponse,
    StorageInfoResponse,
    StoragePruneResponse,
    WorktreeStorageItem,
)
from agy_automation.core.cleanup import cleanup_worktree
from agy_automation.core.logging import get_default_runs_dir, get_logger

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


def format_bytes(num_bytes: int) -> str:
    """Format byte count into human-readable string (e.g. '230 MB')."""
    val = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(val) < 1024.0:
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} PB"


def get_directory_size(path: Path) -> int:
    """Calculate directory size in bytes without following symlinks."""
    total = 0
    if not path.exists():
        return 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += get_directory_size(Path(entry.path))
            except Exception:
                continue
    except Exception:
        pass
    return total


def get_storage_info(db: Session, project_id: Optional[str] = None) -> StorageInfoResponse:
    """Retrieve detailed storage consumption breakdown for active project."""
    project = projects_repo.get_by_id(db, project_id) if project_id else projects_repo.get_active(db)
    if not project:
        return StorageInfoResponse(
            project_id="",
            project_name="None",
            worktrees_total_count=0,
            worktrees_orphaned_count=0,
            worktrees_total_bytes=0,
            worktrees_total_human="0 B",
            runs_logs_bytes=0,
            runs_logs_human="0 B",
            containers_count=0,
            items=[],
        )

    repo_dir = Path(project.path)
    worktrees_dir = repo_dir / ".worktrees"
    items: List[WorktreeStorageItem] = []
    total_bytes = 0

    # 1. Fetch active runs to determine protected worktrees
    all_runs = runs_repo.list_by_project(db, project.id, limit=200)
    active_statuses = {RunStatus.RUNNING.value, RunStatus.AWAITING_REVIEW.value, RunStatus.QUEUED.value}
    active_worktrees = {r.worktree_name: r for r in all_runs if r.status in active_statuses and r.worktree_name}
    run_by_worktree = {r.worktree_name: r for r in all_runs if r.worktree_name}

    # 2. Fetch active chat sessions
    active_chat_sessions = chat_manager.list_sessions()
    active_chat_worktrees = {
        s.worktree_name: s for s in active_chat_sessions if s.status == "ACTIVE" and s.project_id == project.id
    }

    if worktrees_dir.is_dir():
        for entry in worktrees_dir.iterdir():
            if entry.is_dir():
                wt_name = entry.name
                is_active = (wt_name in active_worktrees) or (wt_name in active_chat_worktrees)
                size_b = get_directory_size(entry)
                total_bytes += size_b

                linked_run = run_by_worktree.get(wt_name)
                branch_name = linked_run.branch_name if linked_run else None

                items.append(
                    WorktreeStorageItem(
                        name=wt_name,
                        path=str(entry),
                        size_bytes=size_b,
                        size_human=format_bytes(size_b),
                        is_orphaned=not is_active,
                        run_id=linked_run.id if linked_run else None,
                        branch_name=branch_name,
                    )
                )

    # Sort items: orphaned first, then largest first
    items.sort(key=lambda x: (not x.is_orphaned, -x.size_bytes))
    orphaned_count = sum(1 for item in items if item.is_orphaned)

    # 3. Calculate run logs size
    runs_dir = get_default_runs_dir()
    runs_logs_bytes = get_directory_size(runs_dir) if runs_dir.exists() else 0

    # 4. Count sandbox containers
    containers_count = 0
    for engine_cmd in ("podman", "docker"):
        engine_bin = shutil.which(engine_cmd)
        if engine_bin:
            try:
                res = subprocess.run(
                    [engine_bin, "ps", "-a", "--filter", "name=agy-", "-q"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    lines = [ln.strip() for ln in res.stdout.strip().splitlines() if ln.strip()]
                    containers_count += len(lines)
            except Exception:
                pass

    return StorageInfoResponse(
        project_id=project.id,
        project_name=project.name,
        worktrees_total_count=len(items),
        worktrees_orphaned_count=orphaned_count,
        worktrees_total_bytes=total_bytes,
        worktrees_total_human=format_bytes(total_bytes),
        runs_logs_bytes=runs_logs_bytes,
        runs_logs_human=format_bytes(runs_logs_bytes),
        containers_count=containers_count,
        items=items,
    )


def prune_storage(db: Session, project_id: Optional[str] = None) -> StoragePruneResponse:
    """Safely delete orphaned worktrees and stopped sandbox containers."""
    project = projects_repo.get_by_id(db, project_id) if project_id else projects_repo.get_active(db)
    if not project:
        return StoragePruneResponse(
            pruned_worktrees=[],
            reclaimed_bytes=0,
            reclaimed_human="0 B",
            pruned_containers=0,
            message="No active project found.",
        )

    # 1. Sweep stale chat sessions first
    chat_manager.sweep_stale_sessions(db, max_age_seconds=7200.0)

    # 2. Get current storage info
    info = get_storage_info(db, project_id=project.id)
    repo_dir = Path(project.path)
    pruned_wts = []
    reclaimed_bytes = 0

    for item in info.items:
        if item.is_orphaned:
            try:
                cleanup_worktree(item.name, item.branch_name or "", force=True, repo_dir=repo_dir)
                pruned_wts.append(item.name)
                reclaimed_bytes += item.size_bytes
                logger.info("Pruned orphaned worktree %s (%s)", item.name, item.size_human)
            except Exception as exc:
                logger.warning("Failed to prune worktree %s: %s", item.name, exc)

    # 3. Prune stopped containers
    pruned_containers = 0
    for engine_cmd in ("podman", "docker"):
        engine_bin = shutil.which(engine_cmd)
        if engine_bin:
            try:
                # Find exited or created agy containers
                res = subprocess.run(
                    [engine_bin, "ps", "-a", "--filter", "name=agy-", "--filter", "status=exited", "-q"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                )
                res_created = subprocess.run(
                    [engine_bin, "ps", "-a", "--filter", "name=agy-", "--filter", "status=created", "-q"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                )
                c_ids = set()
                if res.returncode == 0:
                    c_ids.update(line.strip() for line in res.stdout.splitlines() if line.strip())
                if res_created.returncode == 0:
                    c_ids.update(line.strip() for line in res_created.stdout.splitlines() if line.strip())

                if c_ids:
                    subprocess.run(
                        [engine_bin, "rm", "-f", *c_ids],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                    )
                    pruned_containers += len(c_ids)
            except Exception as exc:
                logger.warning("Failed to prune containers with %s: %s", engine_cmd, exc)

    return StoragePruneResponse(
        pruned_worktrees=pruned_wts,
        reclaimed_bytes=reclaimed_bytes,
        reclaimed_human=format_bytes(reclaimed_bytes),
        pruned_containers=pruned_containers,
        message=f"Cleaned up {len(pruned_wts)} worktree(s) and {pruned_containers} container(s), reclaiming {format_bytes(reclaimed_bytes)}.",
    )
