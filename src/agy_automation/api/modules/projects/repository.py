"""SQLAlchemy repository for Projects persistence."""

from typing import List, Optional, Tuple

from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from agy_automation.api.modules.projects.models import Project, utc_now
from agy_automation.api.modules.projects.service import ValidatedProjectMetadata
from agy_automation.core.logging import get_logger

logger = get_logger("agy_automation.api.projects.repo")


def get_by_id(db: Session, project_id: str) -> Optional[Project]:
    """Retrieve project by unique primary key ID."""
    stmt = select(Project).where(Project.id == project_id)
    return db.scalars(stmt).first()


def get_by_path(db: Session, path_str: str) -> Optional[Project]:
    """Retrieve project by exact filesystem path."""
    stmt = select(Project).where(Project.path == path_str)
    return db.scalars(stmt).first()


def get_active(db: Session) -> Optional[Project]:
    """Retrieve the single active project if any."""
    stmt = select(Project).where(Project.is_active.is_(True))
    return db.scalars(stmt).first()


def list_all(db: Session) -> List[Project]:
    """List all registered projects ordered by creation time descending."""
    stmt = select(Project).order_by(desc(Project.created_at))
    return list(db.scalars(stmt).all())


def register_or_update(
    db: Session,
    meta: ValidatedProjectMetadata,
) -> Tuple[Project, bool]:
    """Idempotently register a project or update its metadata.
    
    Returns (project, is_new_registration).
    The first registered project is automatically marked active.
    """
    existing = get_by_path(db, meta.path)
    if existing:
        logger.info("Project already registered at %s. Updating metadata.", meta.path)
        existing.name = meta.name
        existing.git_remote = meta.git_remote
        existing.git_branch = meta.git_branch
        existing.instructions_path = meta.instructions_path
        existing.updated_at = utc_now()
        db.commit()
        db.refresh(existing)
        return existing, False

    # Check if this is the very first project
    total_count = db.query(Project).count()
    should_activate = (total_count == 0)

    project = Project(
        name=meta.name,
        path=meta.path,
        git_remote=meta.git_remote,
        git_branch=meta.git_branch,
        instructions_path=meta.instructions_path,
        is_active=should_activate,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("New project registered: %s (id=%s, active=%s)", project.name, project.id, project.is_active)
    return project, True


def set_active(db: Session, project_id: str) -> Optional[Project]:
    """Atomically set the specified project as the single active project."""
    target = get_by_id(db, project_id)
    if not target:
        return None

    # Deactivate all projects atomically
    db.execute(update(Project).values(is_active=False))
    # Activate target
    target.is_active = True
    target.updated_at = utc_now()
    db.commit()
    db.refresh(target)
    logger.info("Switched active project to: %s (id=%s)", target.name, target.id)
    return target


def delete_project(db: Session, project_id: str) -> bool:
    """Delete a project by ID.
    
    If the active project was deleted, automatically promotes the most
    recently created remaining project to active.
    """
    target = get_by_id(db, project_id)
    if not target:
        return False

    was_active = target.is_active
    db.delete(target)
    db.commit()
    logger.info("Deleted project: id=%s (was_active=%s)", project_id, was_active)

    if was_active:
        remaining = list_all(db)
        if remaining:
            remaining[0].is_active = True
            db.commit()
            logger.info("Promoted next project to active: %s", remaining[0].id)

    return True
