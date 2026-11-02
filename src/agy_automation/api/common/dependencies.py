"""Shared FastAPI dependencies for API modules."""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from agy_automation.api.common.database import get_db
from agy_automation.api.modules.projects.models import Project
from agy_automation.api.modules.projects.repository import get_active


def require_active_project(db: Session = Depends(get_db)) -> Project:
    """Dependency that ensures an active project is selected.
    
    Can be used by downstream modules (like /runs or /containers) to safeguard
    endpoints requiring an active project context.
    """
    project = get_active(db)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active project selected. Please select a project first via /api/projects.",
        )
    return project
