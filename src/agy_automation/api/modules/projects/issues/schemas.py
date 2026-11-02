"""Pydantic v2 schemas for Projects Issues sub-module."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class IssueListItem(BaseModel):
    """Summarized issue metadata for listing views."""

    number: int
    title: str
    state: str
    author: str
    labels: List[str] = Field(default_factory=list)
    updated_at: str = ""
    url: str = ""


class IssueListResponse(BaseModel):
    """Schema returned when listing issues for a project."""

    issues: List[IssueListItem]
    total: int
    state: str


class IssueDetail(BaseModel):
    """Full issue details including author, labels, body, and bundled markdown context."""

    number: int
    title: str
    body: str = ""
    state: str = "OPEN"
    author: str = "Unknown"
    labels: List[str] = Field(default_factory=list)
    url: str = ""
    comments_count: int = 0
    context_markdown: str = ""


class IssueCreateRequest(BaseModel):
    """Payload to formulate and create a new GitHub issue in the target project."""

    title: str
    body: str
    labels: Optional[List[str]] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Issue title cannot be empty")
        return cleaned

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Issue body cannot be empty")
        return cleaned


class IssueProviderStatusResponse(BaseModel):
    """Health and connectivity status of the project's GitHub issue tracking provider."""

    available: bool
    gh_installed: bool
    authenticated: bool
    has_remote: bool
    remote_url: str = ""
    reason: Optional[str] = None
