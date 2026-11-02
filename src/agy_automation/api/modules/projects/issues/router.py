"""FastAPI HTTP router for Project Issues endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from agy_automation.api.common.database import get_db
from agy_automation.api.common.dependencies import require_active_project
from agy_automation.api.modules.projects import repository
from agy_automation.api.modules.projects.issues import service
from agy_automation.api.modules.projects.issues.schemas import (
    IssueCreateRequest,
    IssueDetail,
    IssueListResponse,
    IssueProviderStatusResponse,
)
from agy_automation.api.modules.projects.models import Project

router = APIRouter(tags=["issues"])


# ---------------------------------------------------------
# Active Project Endpoints (Safeguarded by require_active_project)
# ---------------------------------------------------------

@router.get(
    "/active/issues/status",
    response_model=IssueProviderStatusResponse,
    summary="Check issue tracking provider availability for active project",
)
def get_active_project_issue_status(
    active_project: Project = Depends(require_active_project),
):
    """Inspect GitHub CLI connectivity and authentication for the active project."""
    return service.get_provider_status_for_project(active_project)


@router.get(
    "/active/issues",
    response_model=IssueListResponse,
    summary="List issues for the active project",
)
def list_active_project_issues(
    state: str = Query("open", description="Issue state: open, closed, or all"),
    limit: int = Query(30, ge=1, le=100, description="Max issues to fetch"),
    active_project: Project = Depends(require_active_project),
):
    """Retrieve issues from GitHub for the currently active project."""
    return service.list_issues_for_project(active_project, state=state, limit=limit)


@router.get(
    "/active/issues/{issue_number}",
    response_model=IssueDetail,
    summary="Get issue details and context markdown for the active project",
)
def get_active_project_issue(
    issue_number: int,
    active_project: Project = Depends(require_active_project),
):
    """Retrieve full details, comments, and formatted context markdown for an issue."""
    return service.get_issue_detail_for_project(active_project, issue_number)


@router.post(
    "/active/issues",
    response_model=IssueDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new issue in the active project",
)
def create_active_project_issue(
    payload: IssueCreateRequest,
    active_project: Project = Depends(require_active_project),
):
    """Formulate and publish a new GitHub issue in the active project repository."""
    return service.create_issue_for_project(active_project, payload)


# ---------------------------------------------------------
# Specific Project Endpoints (By Project ID)
# ---------------------------------------------------------

def _resolve_project_or_404(project_id: str, db: Session) -> Project:
    project = repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )
    return project


@router.get(
    "/{project_id}/issues",
    response_model=IssueListResponse,
    summary="List issues for a specific project by ID",
)
def list_project_issues_by_id(
    project_id: str,
    state: str = Query("open", description="Issue state: open, closed, or all"),
    limit: int = Query(30, ge=1, le=100, description="Max issues to fetch"),
    db: Session = Depends(get_db),
):
    """Retrieve issues from GitHub for the specified project ID."""
    project = _resolve_project_or_404(project_id, db)
    return service.list_issues_for_project(project, state=state, limit=limit)


@router.get(
    "/{project_id}/issues/{issue_number}",
    response_model=IssueDetail,
    summary="Get issue details for a specific project by ID",
)
def get_project_issue_by_id(
    project_id: str,
    issue_number: int,
    db: Session = Depends(get_db),
):
    """Retrieve full issue payload for the specified project ID."""
    project = _resolve_project_or_404(project_id, db)
    return service.get_issue_detail_for_project(project, issue_number)
