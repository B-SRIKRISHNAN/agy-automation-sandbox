"""Service and in-memory lifecycle manager for Runs."""

import shutil
import subprocess
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agy_automation.api.common.database import SessionLocal
from agy_automation.api.modules.projects import repository as projects_repo
from agy_automation.api.modules.runs import repository as runs_repo
from agy_automation.api.modules.runs.models import Run
from agy_automation.api.modules.runs.schemas import (
    RunCreateRequest,
    RunDiffResponse,
    RunReviewRequest,
    RunReviewResponse,
    RunStatus,
)
from agy_automation.core.cleanup import cleanup_worktree
from agy_automation.core.context import CallerMode, PipelineContext
from agy_automation.core.engine import derive_container_names
from agy_automation.core.git import is_branch_existing
from agy_automation.core.logging import get_logger
from agy_automation.core.orchestrator import run_pipeline
from agy_automation.core.push import push_changes
from agy_automation.core.review_merge import prepare_review_data, review_and_merge

logger = get_logger("agy_automation.api.runs.service")

DEFAULT_MAX_RUNTIME_SECONDS = 2700.0  # 45 minutes execution watchdog limit


class RunManager:
    """Thread-safe coordination manager for active background runs."""

    def __init__(self) -> None:
        self._events: Dict[str, threading.Event] = {}
        self._decisions: Dict[str, bool] = {}
        self._push_decisions: Dict[str, bool] = {}
        self._resolved: set = set()
        self._timed_out: set = set()
        self._aborted: set = set()
        self._run_locks: Dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    @contextmanager
    def run_lock(self, run_id: str):
        """Acquire a per-run execution lock to serialize concurrent reviews or state mutations."""
        with self._lock:
            if run_id not in self._run_locks:
                self._run_locks[run_id] = threading.Lock()
            lock = self._run_locks[run_id]

        with lock:
            yield

    def register_run(self, run_id: str) -> None:
        """Register a new run with an unresolved decision event."""
        with self._lock:
            self._events[run_id] = threading.Event()
            self._decisions[run_id] = False
            self._push_decisions[run_id] = False
            self._resolved.discard(run_id)
            self._timed_out.discard(run_id)
            self._aborted.discard(run_id)

    def is_waiting(self, run_id: str) -> bool:
        """Check if an active thread is registered and awaiting review for run_id."""
        with self._lock:
            return run_id in self._events and not self._events[run_id].is_set()

    def request_abort(self, run_id: str) -> None:
        """Mark run as aborted and unblock any waiting worker thread."""
        with self._lock:
            self._aborted.add(run_id)
            self._decisions[run_id] = False
            self._resolved.add(run_id)
            event = self._events.get(run_id)
            if event:
                event.set()

    def is_aborted(self, run_id: str) -> bool:
        """Check if run was requested to abort."""
        with self._lock:
            return run_id in self._aborted

    def is_rejected(self, run_id: str) -> bool:
        """Check if user explicitly submitted a rejection decision."""
        with self._lock:
            return run_id in self._resolved and not self._decisions.get(run_id, False)

    def wait_for_decision(self, run_id: str, timeout: float = 1800.0) -> bool:
        """Pause current worker thread until review decision is submitted or timeout expires."""
        event = None
        with self._lock:
            event = self._events.get(run_id)

        if event is None:
            logger.warning("No event found for run %s. Defaulting decision to False.", run_id)
            return False

        logger.info("Worker thread for run %s pausing at review gate (timeout=%ss)...", run_id, timeout)
        received = event.wait(timeout=timeout)
        if not received:
            logger.warning("Run %s timed out waiting for review decision.", run_id)
            with self._lock:
                self._timed_out.add(run_id)
            return False

        with self._lock:
            return self._decisions.get(run_id, False)

    def resolve_decision(self, run_id: str, approved: bool, push: bool = False) -> bool:
        """Resolve the review decision, unblocking any waiting worker thread."""
        with self._lock:
            event = self._events.get(run_id)
            if not event:
                return False
            self._decisions[run_id] = approved
            self._push_decisions[run_id] = push
            self._resolved.add(run_id)
            event.set()
            return True

    def get_push_decision(self, run_id: str) -> bool:
        """Return whether user opted to push merged changes."""
        with self._lock:
            return self._push_decisions.get(run_id, False)

    def cleanup_run(self, run_id: str) -> None:
        """Remove in-memory tracking for a completed run."""
        with self._lock:
            self._events.pop(run_id, None)
            self._decisions.pop(run_id, None)
            self._push_decisions.pop(run_id, None)
            self._resolved.discard(run_id)
            self._timed_out.discard(run_id)
            self._aborted.discard(run_id)


# Global process singleton
run_manager = RunManager()


def generate_run_id() -> str:
    """Generate unique run identifier."""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    return f"run_{now_str}_{rand_suffix}"


def start_run(db: Session, request: RunCreateRequest) -> Run:
    """Initiate an automated run in the background."""
    if request.project_id:
        project = projects_repo.get_by_id(db, request.project_id)
    else:
        project = projects_repo.get_active(db)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active project found. Please register and select a project first.",
        )

    run_id = generate_run_id()
    context = PipelineContext(
        target_repo=Path(project.path),
        target_type=request.target_type,
        target_id=request.target_id,
        base_branch=project.git_branch or "master",
        engine=request.engine,
        auto_approve=request.auto_approve,
        caller_mode=CallerMode.API,
        run_id=run_id,
        conversation_id=request.conversation_id,
    )

    run = Run(
        id=run_id,
        project_id=project.id,
        target_type=request.target_type,
        target_id=request.target_id,
        status=RunStatus.QUEUED.value,
        worktree_name=context.worktree_name,
        branch_name=context.branch_name,
        container_name=context.container_name,
        base_branch=project.git_branch or "master",
        auto_approve=request.auto_approve,
        engine=request.engine,
        conversation_id=request.conversation_id,
    )
    run = runs_repo.create(db, run)
    run_manager.register_run(run_id)

    def _worker() -> None:
        worker_db = SessionLocal()

        # Setup execution watchdog timer to prevent infinite loops (45 mins)
        def _watchdog_fire():
            logger.warning("Execution watchdog fired for run %s: exceeded max runtime limit (%ss)", run_id, DEFAULT_MAX_RUNTIME_SECONDS)
            try:
                with SessionLocal() as db_session:
                    abort_run(db_session, run_id, clean_worktree=True, reason=f"Execution timed out after {int(DEFAULT_MAX_RUNTIME_SECONDS // 60)} minutes (watchdog triggered).")
            except Exception as w_exc:
                logger.error("Error during watchdog abort for run %s: %s", run_id, w_exc)

        watchdog = threading.Timer(DEFAULT_MAX_RUNTIME_SECONDS, _watchdog_fire)
        watchdog.daemon = True
        watchdog.start()

        try:
            runs_repo.update_status(worker_db, run_id, RunStatus.RUNNING.value)

            def _approval_hook() -> bool:
                # Callback invoked from Step 4 inside run_pipeline
                log_dir_str = str(context.session_logger.run_dir) if context.session_logger else None
                runs_repo.update_details(
                    worker_db,
                    run_id,
                    worktree_name=context.worktree_name,
                    branch_name=context.branch_name,
                    container_name=context.container_name,
                    base_branch=context.base_branch,
                    log_dir=log_dir_str,
                    conversation_id=context.conversation_id,
                )
                runs_repo.update_status(worker_db, run_id, RunStatus.AWAITING_REVIEW.value)
                return run_manager.wait_for_decision(run_id)

            def _push_hook() -> bool:
                return run_manager.get_push_decision(run_id)

            context.approval_callback = _approval_hook
            context.push_callback = _push_hook
            exit_code = run_pipeline(context=context)

            log_dir_str = str(context.session_logger.run_dir) if context.session_logger else None
            runs_repo.update_details(
                worker_db,
                run_id,
                worktree_name=context.worktree_name,
                branch_name=context.branch_name,
                container_name=context.container_name,
                base_branch=context.base_branch,
                log_dir=log_dir_str,
            )

            if run_manager.is_aborted(run_id):
                runs_repo.update_status(worker_db, run_id, RunStatus.ABORTED.value, error_message="Aborted by user request.", finished=True)
                return

            if exit_code == 0:
                is_merged = getattr(context, "merged", False)
                if is_merged:
                    runs_repo.update_status(worker_db, run_id, RunStatus.COMPLETED.value, finished=True)
                elif run_manager.is_rejected(run_id):
                    repo_dir = Path(project.path)
                    if repo_dir.exists() and context.worktree_name:
                        try:
                            cleanup_worktree(context.worktree_name, context.branch_name or "", force=True, repo_dir=repo_dir)
                        except Exception as c_exc:
                            logger.warning("Failed to clean rejected worktree %s: %s", context.worktree_name, c_exc)
                    runs_repo.update_status(worker_db, run_id, RunStatus.ABORTED.value, error_message="Review rejected by user.", finished=True)
                else:
                    logger.info(
                        "Worker thread finished for run %s. Worktree is preserved; keeping status AWAITING_REVIEW for offline resumption.",
                        run_id,
                    )
                    runs_repo.update_status(worker_db, run_id, RunStatus.AWAITING_REVIEW.value, finished=False)
            else:
                err_msg = f"Pipeline execution failed with exit code {exit_code}"
                runs_repo.update_status(worker_db, run_id, RunStatus.FAILED.value, error_message=err_msg, finished=True)

        except Exception as exc:
            if run_manager.is_aborted(run_id):
                runs_repo.update_status(worker_db, run_id, RunStatus.ABORTED.value, error_message="Aborted by user request.", finished=True)
            else:
                logger.exception("Background execution failed for run %s: %s", run_id, exc)
                runs_repo.update_status(
                    worker_db,
                    run_id,
                    RunStatus.FAILED.value,
                    error_message=str(exc),
                    finished=True,
                )
        finally:
            watchdog.cancel()
            run_manager.cleanup_run(run_id)
            worker_db.close()

    thread = threading.Thread(target=_worker, daemon=True, name=f"run-worker-{run_id}")
    thread.start()

    return run


def get_run(db: Session, run_id: str) -> Run:
    """Retrieve run record by ID or raise 404."""
    run = runs_repo.get_by_id(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )
    return run


def list_runs(
    db: Session,
    project_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
) -> List[Run]:
    """List runs for active or specified project."""
    if not project_id:
        active = projects_repo.get_active(db)
        if active:
            project_id = active.id

    return runs_repo.list_by_project(db, project_id=project_id, status=status_filter, limit=limit)


def _extract_summary(run: Run) -> Optional[str]:
    """Extract AI resolution summary from summary.md, metadata.json, or events.jsonl."""
    if not run.log_dir:
        return None
    log_dir_path = Path(run.log_dir)
    if not log_dir_path.exists():
        return None

    summary_file = log_dir_path / "summary.md"
    if summary_file.is_file():
        try:
            content = summary_file.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception:
            pass

    meta_file = log_dir_path / "metadata.json"
    if meta_file.is_file():
        try:
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
            summary_content = meta_data.get("results", {}).get("summary")
            if summary_content:
                return str(summary_content).strip()
        except Exception:
            pass

    events_file = log_dir_path / "events.jsonl"
    if events_file.is_file():
        try:
            with open(events_file, "r", encoding="utf-8") as f:
                for line in f:
                    if '"event": "result"' in line:
                        parsed = json.loads(line)
                        res = parsed.get("data", {}).get("result", {})
                        summary_content = res.get("response")
                        if summary_content:
                            return str(summary_content).strip()
        except Exception:
            pass

    return None


def get_run_diff(db: Session, run_id: str) -> RunDiffResponse:
    """Inspect git diff and AI summary for a run worktree."""
    run = get_run(db, run_id)
    project = projects_repo.get_by_id(db, run.project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated project not found.")

    summary = _extract_summary(run)

    if not run.worktree_name or not run.branch_name:
        return RunDiffResponse(
            run_id=run.id,
            worktree_name=run.worktree_name,
            branch_name=run.branch_name,
            base_branch=run.base_branch,
            diff_stat="",
            diff_snippet="",
            commits=[],
            summary=summary,
        )

    try:
        review_data = prepare_review_data(
            worktree_name=run.worktree_name,
            branch_name=run.branch_name,
            base_branch=run.base_branch,
            repo_dir=Path(project.path),
        )
        return RunDiffResponse(
            run_id=run.id,
            worktree_name=run.worktree_name,
            branch_name=run.branch_name,
            base_branch=run.base_branch,
            diff_stat=review_data.get("diff_stat", ""),
            diff_snippet=review_data.get("diff_snippet", ""),
            commits=review_data.get("commits", []),
            summary=summary,
        )
    except Exception as exc:
        logger.error("Failed to prepare diff for run %s: %s", run_id, exc)
        return RunDiffResponse(
            run_id=run.id,
            worktree_name=run.worktree_name,
            branch_name=run.branch_name,
            base_branch=run.base_branch,
            diff_stat="",
            diff_snippet=f"Diff generation failed: {exc}",
            commits=[],
            summary=summary,
        )


def submit_review(db: Session, run_id: str, request: RunReviewRequest) -> RunReviewResponse:
    """Submit approval or rejection for a run awaiting review with concurrency locking and idempotency."""
    with run_manager.run_lock(run_id):
        # Refresh run state within the lock
        run = get_run(db, run_id)

        # Idempotency: If already completed by a concurrent request, return success immediately
        if run.status == RunStatus.COMPLETED.value:
            return RunReviewResponse(
                run_id=run_id,
                status=RunStatus.COMPLETED.value,
                merged=True,
                pushed=bool(request.push),
                message="Run changes are already merged and finalized.",
            )

        if run.status != RunStatus.AWAITING_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Run '{run_id}' is not awaiting review (current status: {run.status}).",
            )

        project = projects_repo.get_by_id(db, run.project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated project not found.")

        # 1. Active Worker Path: unblock the waiting thread
        if run_manager.is_waiting(run_id):
            run_manager.resolve_decision(run_id, approved=request.approved, push=request.push)
            return RunReviewResponse(
                run_id=run_id,
                status="PROCESSING",
                merged=request.approved,
                pushed=request.push,
                message="Decision submitted to active background worker.",
            )

        # 2. Resumption Path: worker exited or server rebooted
        if not request.approved:
            repo_dir = Path(project.path)
            if repo_dir.exists() and run.worktree_name:
                try:
                    cleanup_worktree(run.worktree_name, run.branch_name or "", force=True, repo_dir=repo_dir)
                except Exception as exc:
                    logger.warning("Failed to cleanup rejected worktree %s for run %s: %s", run.worktree_name, run_id, exc)
            runs_repo.update_status(db, run_id, RunStatus.ABORTED.value, finished=True)
            return RunReviewResponse(
                run_id=run_id,
                status=RunStatus.ABORTED.value,
                merged=False,
                pushed=False,
                message="Run review rejected, worktree cleaned up, and status marked ABORTED.",
            )

        merged = False
        pushed = False
        repo_dir = Path(project.path)

        # Pre-check idempotency: if branch and worktree directory are already cleaned up, changes were already merged
        if repo_dir.exists() and run.branch_name and not is_branch_existing(run.branch_name, repo_dir):
            worktree_dir = repo_dir / ".worktrees" / (run.worktree_name or "")
            if not worktree_dir.exists():
                logger.info("Run %s branch %s is already merged into %s. Finalizing as COMPLETED.", run_id, run.branch_name, run.base_branch)
                runs_repo.update_status(db, run_id, RunStatus.COMPLETED.value, finished=True)
                return RunReviewResponse(
                    run_id=run_id,
                    status=RunStatus.COMPLETED.value,
                    merged=True,
                    pushed=bool(request.push),
                    message="Run changes are already merged and finalized.",
                )

        try:
            merged = review_and_merge(
                worktree_name=run.worktree_name or "",
                branch_name=run.branch_name or "",
                base_branch=run.base_branch,
                auto_approve=True,
                interactive=False,
                repo_dir=repo_dir,
            )

            # Post-check: If review_and_merge finished and the branch was deleted during cleanup, merge succeeded
            if not merged and repo_dir.exists() and run.branch_name and not is_branch_existing(run.branch_name, repo_dir):
                merged = True

            if not merged:
                runs_repo.update_status(db, run_id, RunStatus.FAILED.value, error_message="Merge failed.", finished=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to merge run branch into base branch.",
                )

            if request.push:
                pushed = bool(
                    push_changes(
                        branch_name=run.base_branch,
                        auto_approve=True,
                        interactive=False,
                        repo_dir=repo_dir,
                    )
                )
            runs_repo.update_status(db, run_id, RunStatus.COMPLETED.value, finished=True)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Resumed merge failed for run %s: %s", run_id, exc)
            runs_repo.update_status(db, run_id, RunStatus.FAILED.value, error_message=str(exc), finished=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to merge and finalize run: {exc}",
            )

        return RunReviewResponse(
            run_id=run_id,
            status=RunStatus.COMPLETED.value,
            merged=merged,
            pushed=pushed,
            message="Run merged and finalized successfully from persisted state.",
        )


def abort_run(
    db: Session,
    run_id: str,
    clean_worktree: bool = True,
    reason: str = "Aborted by user request.",
) -> Run:
    """Abort an active, queued, or awaiting-review run immediately and clean up worktree."""
    run = get_run(db, run_id)
    project = projects_repo.get_by_id(db, run.project_id)
    repo_dir = Path(project.path) if project else None

    if run.status in (RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.ABORTED.value):
        if clean_worktree and run.worktree_name and repo_dir and repo_dir.exists():
            try:
                cleanup_worktree(run.worktree_name, run.branch_name or "", force=True, repo_dir=repo_dir)
            except Exception as exc:
                logger.warning("Could not clean worktree %s for finished run %s: %s", run.worktree_name, run_id, exc)
        return run

    run_manager.request_abort(run_id)

    target_container = run.container_name
    if not target_container and repo_dir:
        target_container, _ = derive_container_names(repo_dir, worktree_name=run.worktree_name or "")

    if target_container:
        try:
            for engine_cmd in ("podman", "docker"):
                engine_bin = shutil.which(engine_cmd)
                if engine_bin:
                    subprocess.run(
                        [engine_bin, "rm", "-f", target_container],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
        except Exception as exc:
            logger.warning("Could not terminate container %s for run %s: %s", target_container, run_id, exc)

    if clean_worktree and run.worktree_name and repo_dir and repo_dir.exists():
        try:
            cleanup_worktree(run.worktree_name, run.branch_name or "", force=True, repo_dir=repo_dir)
        except Exception as exc:
            logger.warning("Could not clean worktree %s for aborted run %s: %s", run.worktree_name, run_id, exc)

    updated = runs_repo.update_status(
        db,
        run_id,
        RunStatus.ABORTED.value,
        error_message=reason,
        finished=True,
    )
    return updated or run
