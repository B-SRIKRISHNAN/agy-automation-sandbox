"""Pydantic v2 schemas for Projects module."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ProjectCreate(BaseModel):
    """Schema for registering a new project by absolute path."""

    path: str

    @field_validator("path")
    @classmethod
    def validate_absolute_path(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Project path cannot be empty")
        p = Path(cleaned)
        if not p.is_absolute():
            raise ValueError(f"Project path must be an absolute path: received '{cleaned}'")
        return str(p.resolve())


class ProjectResponse(BaseModel):
    """Schema representing project details returned to API clients."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    path: str
    git_remote: str
    git_branch: str
    instructions_path: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """Schema for listing projects."""

    projects: List[ProjectResponse]
    total: int
