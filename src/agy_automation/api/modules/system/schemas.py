"""Pydantic v2 schemas for system telemetry and agy quota."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class QuotaBucket(BaseModel):
    """Specific quota window (e.g. 5h rolling or weekly)."""
    id: str = Field(..., description="Unique bucket identifier, e.g. 'gemini-5h'")
    name: str = Field(..., description="Display name, e.g. 'Five Hour Limit Remaining'")
    description: Optional[str] = Field(None, description="Human explanation of bucket state")
    window: str = Field(..., description="Time window, e.g. '5h' or 'weekly'")
    remaining_fraction: float = Field(..., description="Fraction of quota remaining (0.0 to 1.0)")
    remaining_percent: int = Field(..., description="Percentage of quota remaining (0 to 100)")
    reset_time: Optional[str] = Field(None, description="ISO timestamp when quota window resets")


class QuotaGroup(BaseModel):
    """Model family sharing a quota pool (e.g. Gemini Models, Claude & GPT)."""
    name: str = Field(..., description="Group name, e.g. 'Gemini Models'")
    description: Optional[str] = Field(None, description="Models included in this quota pool")
    buckets: List[QuotaBucket] = Field(default_factory=list, description="Associated quota buckets")


class QuotaResponse(BaseModel):
    """Complete quota usage status response."""
    description: Optional[str] = Field(None, description="Overview description of quota model")
    groups: List[QuotaGroup] = Field(default_factory=list, description="Model groups with quota data")
    cached: bool = Field(False, description="Whether this response was served from in-memory TTL cache")
    updated_at: datetime = Field(..., description="Timestamp when quota data was fetched")
    error: Optional[str] = Field(None, description="Error message if quota query failed")


class WorktreeStorageItem(BaseModel):
    """Details for a single git worktree in the project directory."""
    name: str = Field(..., description="Worktree folder name")
    path: str = Field(..., description="Absolute filesystem path")
    size_bytes: int = Field(0, description="Size in bytes")
    size_human: str = Field("0 B", description="Human-readable size (e.g. '230 MB')")
    is_orphaned: bool = Field(True, description="True if not associated with an active running or awaiting-review run")
    run_id: Optional[str] = Field(None, description="Linked run ID if any")
    branch_name: Optional[str] = Field(None, description="Git branch name if known")


class StorageInfoResponse(BaseModel):
    """Complete storage consumption breakdown for worktrees, logs, and containers."""
    project_id: str = Field(..., description="Active project ID")
    project_name: str = Field(..., description="Active project name")
    worktrees_total_count: int = Field(0, description="Total worktree directories found")
    worktrees_orphaned_count: int = Field(0, description="Number of orphaned worktrees")
    worktrees_total_bytes: int = Field(0, description="Total size in bytes of all worktrees")
    worktrees_total_human: str = Field("0 B", description="Total size human-formatted")
    runs_logs_bytes: int = Field(0, description="Size of run session logs")
    runs_logs_human: str = Field("0 B", description="Run session logs human-formatted")
    containers_count: int = Field(0, description="Number of sandbox containers detected")
    items: List[WorktreeStorageItem] = Field(default_factory=list, description="List of worktrees")


class StoragePruneResponse(BaseModel):
    """Result of pruning orphaned worktrees and stale containers."""
    pruned_worktrees: List[str] = Field(default_factory=list, description="Names of pruned worktrees")
    reclaimed_bytes: int = Field(0, description="Total bytes freed")
    reclaimed_human: str = Field("0 B", description="Human-formatted reclaimed size")
    pruned_containers: int = Field(0, description="Number of containers removed")
    message: str = Field(..., description="Summary status message")
