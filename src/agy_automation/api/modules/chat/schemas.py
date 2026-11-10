"""Pydantic schemas for interactive AI issue formulation chat sessions."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatSessionCreateRequest(BaseModel):
    """Payload to initiate an interactive formulation session."""
    project_id: Optional[str] = Field(None, description="Project ID. Defaults to active project.")
    initial_prompt: Optional[str] = Field("", description="Initial thought or problem concept.")


class ChatMessageRequest(BaseModel):
    """User message payload sent into an active chat session."""
    content: str = Field(..., min_length=1, description="Message text from the user.")


class ChatMessageResponse(BaseModel):
    """A message in the chat history."""
    role: str = Field(..., description="'user' | 'assistant' | 'system'")
    content: str
    timestamp: datetime = Field(default_factory=utc_now)
    tool_call: Optional[str] = None


class DraftIssue(BaseModel):
    """Structured issue extracted from formulation session."""
    title: str = Field(..., description="Crisp issue title under 70 characters.")
    body: str = Field(..., description="Problem description and expected acceptance criteria.")


class ChatSessionResponse(BaseModel):
    """Metadata and current state of a chat formulation session."""
    session_id: str
    project_id: str
    status: str = Field(..., description="'ACTIVE' | 'TERMINATED' | 'CONVERTED'")
    session_slug: str
    worktree_name: str
    branch_name: str
    conversation_id: Optional[str] = None
    messages: List[ChatMessageResponse] = Field(default_factory=list)
    draft_issue: Optional[DraftIssue] = None
    created_at: datetime
    updated_at: datetime


class CreateAndRunRequest(BaseModel):
    """Payload to finalize draft into a GitHub issue and immediately start the autonomous run."""
    title: str = Field(..., min_length=3, description="Final issue title.")
    body: str = Field(..., min_length=5, description="Final issue description.")
    auto_approve: bool = Field(False, description="Whether the subsequent run auto-approves merges.")
    engine: str = Field("auto", description="Container engine to use.")


class CreateAndRunResponse(BaseModel):
    """Result of issue creation and handoff to run."""
    session_id: str
    issue_number: int
    issue_url: str
    run_id: str
    message: str
