"""SQLAlchemy repository for Runs persistence."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from agy_automation.api.modules.runs.models import Run, utc_now
from agy_automation.core.logging import get_logger

logger = get_logger("agy_automation.api.runs.repo")


def create(db: Session, run: Run) -> Run:
    """Persist a new run record."""
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_by_id(db: Session, run_id: str) -> Optional[Run]:
    """Retrieve run by primary key ID."""
    stmt = select(Run).where(Run.id == run_id)
    return db.scalars(stmt).first()


def list_by_project(
    db: Session,
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Run]:
    """List runs optionally filtered by project_id and status, ordered by created_at descending."""
    stmt = select(Run)
    if project_id:
        stmt = stmt.where(Run.project_id == project_id)
    if status:
        stmt = stmt.where(Run.status == status)
    stmt = stmt.order_by(desc(Run.created_at)).limit(limit)
    return list(db.scalars(stmt).all())


def update_status(
    db: Session,
    run_id: str,
    status: str,
    error_message: Optional[str] = None,
    finished: bool = False,
) -> Optional[Run]:
    """Update execution status, timestamps, and optional error message."""
    run = get_by_id(db, run_id)
    if not run:
        return None
    run.status = status
    run.updated_at = utc_now()
    if error_message is not None:
        run.error_message = error_message
    if finished:
        run.finished_at = utc_now()
    db.commit()
    db.refresh(run)
    return run


def update_details(
    db: Session,
    run_id: str,
    worktree_name: Optional[str] = None,
    branch_name: Optional[str] = None,
    base_branch: Optional[str] = None,
    log_dir: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> Optional[Run]:
    """Update git and logging metadata associated with the run."""
    run = get_by_id(db, run_id)
    if not run:
        return None
    if worktree_name is not None:
        run.worktree_name = worktree_name
    if branch_name is not None:
        run.branch_name = branch_name
    if base_branch is not None:
        run.base_branch = base_branch
    if log_dir is not None:
        run.log_dir = log_dir
    if conversation_id is not None:
        run.conversation_id = conversation_id
    run.updated_at = utc_now()
    db.commit()
    db.refresh(run)
    return run
