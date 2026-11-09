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
