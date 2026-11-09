"""FastAPI router for Runs orchestration and log streaming."""

import asyncio
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agy_automation.api.common.database import get_db
from agy_automation.api.modules.runs import service
from agy_automation.api.modules.runs.schemas import (
    RunCreateRequest,
    RunDiffResponse,
    RunListResponse,
    RunResponse,
    RunReviewRequest,
    RunReviewResponse,
)
from agy_automation.core.logging import get_default_runs_dir, get_logger

logger = get_logger("agy_automation.api.runs.router")

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RunResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def trigger_run(
    request: RunCreateRequest,
    db: Session = Depends(get_db),
) -> RunResponse:
    """Initiate an autonomous or interactive run in the background."""
    run = service.start_run(db, request)
    return RunResponse.model_validate(run)


@router.get("", response_model=RunListResponse)
@router.get("/", response_model=RunListResponse, include_in_schema=False)
def list_runs(
    project_id: Optional[str] = Query(None, description="Filter by project ID. Defaults to active project."),
    status: Optional[str] = Query(None, description="Filter by execution status (QUEUED, RUNNING, etc.)."),
    limit: int = Query(50, ge=1, le=200, description="Max runs to return."),
    db: Session = Depends(get_db),
) -> RunListResponse:
    """List runs for the active project or specified filter."""
    runs = service.list_runs(db, project_id=project_id, status_filter=status, limit=limit)
    return RunListResponse(
        runs=[RunResponse.model_validate(r) for r in runs],
        total=len(runs),
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run_detail(
    run_id: str,
    db: Session = Depends(get_db),
) -> RunResponse:
    """Retrieve detailed state and metadata for a single run."""
    run = service.get_run(db, run_id)
    return RunResponse.model_validate(run)


@router.get("/{run_id}/diff", response_model=RunDiffResponse)
def get_run_diff(
    run_id: str,
    db: Session = Depends(get_db),
) -> RunDiffResponse:
    """Retrieve git diff preview for a run branch awaiting review."""
    return service.get_run_diff(db, run_id)


@router.put("/{run_id}/review", response_model=RunReviewResponse)
def review_run(
    run_id: str,
    request: RunReviewRequest,
    db: Session = Depends(get_db),
) -> RunReviewResponse:
    """Submit approval or rejection for a run in AWAITING_REVIEW status."""
    return service.submit_review(db, run_id, request)


@router.post("/{run_id}/abort", response_model=RunResponse)
def abort_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> RunResponse:
    """Abort an active, queued, or awaiting-review run immediately."""
    run = service.abort_run(db, run_id)
    return RunResponse.model_validate(run)


@router.get("/{run_id}/stream")
async def stream_run_logs(
    run_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream live structured execution events via Server-Sent Events (SSE)."""
    run = service.get_run(db, run_id)

    events_file: Optional[Path] = None
    if run.log_dir:
        cand = Path(run.log_dir) / "events.jsonl"
        if cand.is_file():
            events_file = cand

    if not events_file:
        cand = get_default_runs_dir() / run_id / "events.jsonl"
        events_file = cand

    async def event_generator():
        # 1. Wait briefly for file creation if run just queued
        for _ in range(20):
            if events_file.is_file():
                break
            yield f": ping - waiting for log initialization\n\n"
            await asyncio.sleep(0.2)

        if not events_file.is_file():
            initial_payload = json.dumps({"event": "status", "status": run.status, "message": "Log file not yet created"})
            yield f"data: {initial_payload}\n\n"
            return

        # 2. Stream existing lines and tail for new lines
        with open(events_file, "r", encoding="utf-8") as f:
            while True:
                line = f.readline()
                if line:
                    stripped = line.strip()
                    if stripped:
                        yield f"data: {stripped}\n\n"
                else:
                    # Check current run status from DB
                    # If finished, exit generator
                    cur_run = service.runs_repo.get_by_id(db, run_id)
                    if cur_run and cur_run.status in ("COMPLETED", "FAILED", "ABORTED"):
                        # Read one last time in case new lines flushed
                        rem = f.read().strip()
                        if rem:
                            for rline in rem.splitlines():
                                if rline.strip():
                                    yield f"data: {rline.strip()}\n\n"
                        final_evt = json.dumps({"event": "stream_closed", "status": cur_run.status})
                        yield f"data: {final_evt}\n\n"
                        break

                    await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
