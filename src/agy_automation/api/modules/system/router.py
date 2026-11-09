"""FastAPI router for system telemetry and agy quota endpoints."""

from fastapi import APIRouter, Query

from agy_automation.api.modules.system import service
from agy_automation.api.modules.system.schemas import QuotaResponse

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
