"""FastAPI router for system telemetry and agy quota endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agy_automation.api.common.database import get_db
from agy_automation.api.modules.system import service
from agy_automation.api.modules.system.schemas import (
    QuotaResponse,
    StorageInfoResponse,
    StoragePruneResponse,
)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/quota", response_model=QuotaResponse)
@router.get("/quota/", response_model=QuotaResponse, include_in_schema=False)
def get_agy_quota(
    force_refresh: bool = Query(
        False,
        description="Bypass 60-second in-memory cache and query agy CLI directly.",
    ),
) -> QuotaResponse:
    """Retrieve official Antigravity CLI quota status (5-hour and weekly limits)."""
    return service.fetch_agy_quota(force_refresh=force_refresh)


@router.get("/storage", response_model=StorageInfoResponse)
@router.get("/storage/", response_model=StorageInfoResponse, include_in_schema=False)
def get_storage_breakdown(
    project_id: Optional[str] = Query(None, description="Optional project ID. Defaults to active project."),
    db: Session = Depends(get_db),
) -> StorageInfoResponse:
    """Retrieve storage consumption for worktrees, run logs, and containers."""
    return service.get_storage_info(db, project_id=project_id)


@router.post("/storage/prune", response_model=StoragePruneResponse)
@router.post("/storage/prune/", response_model=StoragePruneResponse, include_in_schema=False)
def prune_storage(
    project_id: Optional[str] = Query(None, description="Optional project ID. Defaults to active project."),
    db: Session = Depends(get_db),
) -> StoragePruneResponse:
    """Safely delete orphaned worktrees, stale branches, and stopped containers."""
    return service.prune_storage(db, project_id=project_id)
