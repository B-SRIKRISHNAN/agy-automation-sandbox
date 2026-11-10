"""FastAPI router for interactive issue formulation chat sessions."""

import asyncio
import json
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agy_automation.api.common.database import get_db
from agy_automation.api.modules.chat import service
from agy_automation.api.modules.chat.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    CreateAndRunRequest,
    CreateAndRunResponse,
)

router = APIRouter(prefix="/chat-sessions", tags=["chat"])


@router.post("", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_chat_session(
    request: ChatSessionCreateRequest,
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    """Initiate an interactive AI issue formulation session with scratch worktree isolation."""
    session_state = service.chat_manager.create_session(db, request)
    return session_state.to_response()


@router.get("/{session_id}", response_model=ChatSessionResponse)
def get_chat_session(session_id: str) -> ChatSessionResponse:
    """Get the current conversation history, status, and draft issue statement."""
    session_state = service.chat_manager.get_session(session_id)
    return session_state.to_response()


@router.post("/{session_id}/messages", response_model=ChatSessionResponse)
def post_chat_message(session_id: str, request: ChatMessageRequest) -> ChatSessionResponse:
    """Send a user message to investigate code or refine requirements."""
    service.chat_manager.post_message(session_id, request.content)
    session_state = service.chat_manager.get_session(session_id)
    return session_state.to_response()


@router.get("/{session_id}/stream")
async def stream_chat_turn(session_id: str) -> StreamingResponse:
    """Stream live token deltas, tool actions, and drafted issues via Server-Sent Events (SSE)."""
    queue = service.chat_manager.register_subscriber(session_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("done", "terminated"):
                        break
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            service.chat_manager.remove_subscriber(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/terminate", response_model=ChatSessionResponse)
def terminate_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    """Immediately terminate the chat session, kill subprocesses, and clean up the worktree."""
    session_state = service.chat_manager.terminate_session(db, session_id)
    return session_state.to_response()


@router.post("/{session_id}/create-and-run", response_model=CreateAndRunResponse)
def create_issue_and_start_run(
    session_id: str,
    request: CreateAndRunRequest,
    db: Session = Depends(get_db),
) -> CreateAndRunResponse:
    """Publish the formulated draft as a real GitHub issue and immediately launch the autonomous runner."""
    return service.chat_manager.create_and_run(db, session_id, request)
