"""FastAPI HTTP router for Projects endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from agy_automation.api.common.database import get_db
from agy_automation.api.modules.projects import repository, service
from agy_automation.api.modules.projects.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    summary="Register or update a local Git repository as a project",
)
def register_project(
    payload: ProjectCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """Register an existing local Git repository by absolute path.
    
    If the project is already registered, updates its metadata and returns 200 OK.
    If the project is new, registers it and returns 201 Created.
    If it is the first project registered, it is automatically marked active.
    """
    metadata = service.inspect_git_repository(payload.path)
    project, created = repository.register_or_update(db, metadata)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return project


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List all registered projects",
)
def list_projects(db: Session = Depends(get_db)):
    """Retrieve all registered projects ordered by creation time descending."""
    projects = repository.list_all(db)
    return ProjectListResponse(projects=projects, total=len(projects))


@router.get(
    "/active",
    response_model=Optional[ProjectResponse],
    summary="Retrieve the currently active project context",
)
def get_active_project(response: Response, db: Session = Depends(get_db)):
    """Retrieve the single active project.
    
    Returns 204 No Content if no project has been registered or activated yet.
    """
    project = repository.get_active(db)
    if not project:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
    return project


@router.post(
    "/{project_id}/select",
    response_model=ProjectResponse,
    summary="Select a project as active",
)
@router.put(
    "/{project_id}/select",
    response_model=ProjectResponse,
    summary="Select a project as active (idempotent PUT alias)",
)
def select_active_project(project_id: str, db: Session = Depends(get_db)):
    """Atomically activate the specified project and deactivate all others."""
    project = repository.set_active(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )
    return project


@router.delete(
    "/{project_id}",
    summary="Delete a registered project",
)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Remove a project from the registry by ID."""
    deleted = repository.delete_project(db, project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )
    return {"deleted": True, "project_id": project_id}


# Mount Issues sub-router
from agy_automation.api.modules.projects.issues.router import router as issues_router

router.include_router(issues_router)
