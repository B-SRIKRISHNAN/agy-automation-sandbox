"""Pydantic v2 schemas for the Runs API module."""

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(str, Enum):
    """Lifecycle statuses for a run."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class RunCreateRequest(BaseModel):
    """Request payload to initiate a new automated or interactive run."""
    project_id: Optional[str] = Field(None, description="Target project ID; defaults to active project if omitted.")
    target_type: Literal["issue", "session"] = Field("issue", description="Execution mode: issue resolution or local session.")
    target_id: str = Field(..., min_length=1, description="Issue number (e.g. '42') or session slug (e.g. 'refactor-auth').")
    auto_approve: bool = Field(False, description="Automatically merge and push without human review.")
    engine: str = Field("auto", description="Container engine: auto, docker, or podman.")
    conversation_id: Optional[str] = Field(None, description="Optional Antigravity conversation ID to resume or link.")


class RunResponse(BaseModel):
    """Full detail response schema for a run."""
    id: str
    project_id: str
    target_type: str
    target_id: str
    status: str
    worktree_name: Optional[str] = None
    container_name: Optional[str] = None
    branch_name: Optional[str] = None
    base_branch: str = "master"
    conversation_id: Optional[str] = None
    log_dir: Optional[str] = None
    auto_approve: bool = False
    engine: str = "auto"
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RunListResponse(BaseModel):
    """Collection wrapper schema for runs."""
    runs: List[RunResponse]
    total: int


class RunReviewRequest(BaseModel):
    """Review decision payload submitted when run status is AWAITING_REVIEW."""
    approved: bool = Field(..., description="True to approve merge, False to reject.")
    push: bool = Field(False, description="True to push merged commits to remote origin.")


class RunReviewResponse(BaseModel):
    """Result of review decision submission."""
    run_id: str
    status: str
    merged: bool
    pushed: bool
    message: str


class RunDiffResponse(BaseModel):
    """Git diff and commits preview for an active run awaiting review."""
    run_id: str
    worktree_name: Optional[str] = None
    container_name: Optional[str] = None
    branch_name: Optional[str] = None
    base_branch: str = "master"
    diff_stat: str = ""
    diff_snippet: str = ""
    commits: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
