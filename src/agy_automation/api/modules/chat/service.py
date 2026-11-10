"""Service managing interactive chat sessions for issue formulation on mobile."""

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agy_automation.api.modules.chat.schemas import (
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    CreateAndRunRequest,
    CreateAndRunResponse,
    DraftIssue,
)
from agy_automation.api.modules.projects import repository as projects_repo
from agy_automation.api.modules.projects.issues import service as issues_service
from agy_automation.api.modules.projects.issues.schemas import IssueCreateRequest
from agy_automation.api.modules.runs import service as runs_service
from agy_automation.api.modules.runs.schemas import RunCreateRequest
from agy_automation.core.cleanup import cleanup_worktree
from agy_automation.core.generate_issue import ISSUE_ANALYST_INSTRUCTIONS, parse_generated_issue
from agy_automation.core.git import sanitize_session_name
from agy_automation.core.logging import get_logger
from agy_automation.core.review_merge import verify_agy_installed
from agy_automation.core.worktree import create_worktree, inject_issue_context

logger = get_logger("agy_automation.api.chat.service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatSessionState:
    """In-memory state of an active interactive chat formulation session."""

    def __init__(
        self,
        session_id: str,
        project_id: str,
        session_slug: str,
        worktree_name: str,
        branch_name: str,
        worktree_path: Path,
        conversation_id: str,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self.session_slug = session_slug
        self.worktree_name = worktree_name
        self.branch_name = branch_name
        self.worktree_path = worktree_path
        self.conversation_id = conversation_id
        self.status = "ACTIVE"  # ACTIVE | TERMINATED | CONVERTED
        self.messages: List[ChatMessageResponse] = []
        self.draft_issue: Optional[DraftIssue] = None
        self.created_at = utc_now()
        self.updated_at = utc_now()
        self.active_proc: Optional[subprocess.Popen] = None
        self.subscribers: List[asyncio.Queue] = []
        self.lock = threading.Lock()

    def to_response(self) -> ChatSessionResponse:
        return ChatSessionResponse(
            session_id=self.session_id,
            project_id=self.project_id,
            status=self.status,
            session_slug=self.session_slug,
            worktree_name=self.worktree_name,
            branch_name=self.branch_name,
            conversation_id=self.conversation_id,
            messages=list(self.messages),
            draft_issue=self.draft_issue,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class ChatSessionManager:
    """Singleton manager tracking and coordinating interactive formulation sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, ChatSessionState] = {}
        self._lock = threading.Lock()

    def create_session(self, db: Session, request: ChatSessionCreateRequest) -> ChatSessionState:
        """Create a scratch worktree and interactive session for issue formulation."""
        project = None
        if request.project_id:
            project = projects_repo.get_by_id(db, request.project_id)
        if not project:
            project = projects_repo.get_active_project(db)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active project selected to start chat session.",
            )

        repo_dir = Path(project.path)
        session_id = f"chat_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        initial_prompt = (request.initial_prompt or "").strip()
        slug_seed = sanitize_session_name(initial_prompt[:20] if initial_prompt else "issue-draft")
        session_slug = f"draft-{slug_seed}-{int(time.time()) % 10000}"
        worktree_name = f"worktree-{session_slug}"
        branch_name = f"session/{session_slug}"
        conversation_id = str(uuid.uuid4())

        logger.info("Creating scratch exploration worktree for chat session %s...", session_id)
        worktree_path = create_worktree(
            worktree_name=worktree_name,
            branch_name=branch_name,
            repo_dir=repo_dir,
            force=True,
            interactive=False,
        )

        # Inject instructions
        instr_file = worktree_path / "AGENT_INSTRUCTIONS.md"
        with open(instr_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(ISSUE_ANALYST_INSTRUCTIONS)

        context_content = f"# Issue Formulation Session\n## Initial Developer Concept\n{initial_prompt or 'Collaborate with the developer to investigate the code and formulate a GitHub issue.'}\n"
        inject_issue_context(worktree_path, context_content)

        session_state = ChatSessionState(
            session_id=session_id,
            project_id=project.id,
            session_slug=session_slug,
            worktree_name=worktree_name,
            branch_name=branch_name,
            worktree_path=worktree_path,
            conversation_id=conversation_id,
        )

        with self._lock:
            self._sessions[session_id] = session_state

        if initial_prompt:
            self.post_message(session_id, initial_prompt)

        return session_state

    def get_session(self, session_id: str) -> ChatSessionState:
        with self._lock:
            session = self._sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat session '{session_id}' not found.")
        return session

    def post_message(self, session_id: str, content: str) -> None:
        """Send a message into the conversation turn and run agy streaming in a background thread."""
        session = self.get_session(session_id)
        if session.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot post message to session with status {session.status}.",
            )

        with session.lock:
            session.messages.append(ChatMessageResponse(role="user", content=content, timestamp=utc_now()))
            session.updated_at = utc_now()

        agy_bin = verify_agy_installed()

        def _turn_worker() -> None:
            cmd = [
                agy_bin,
                "--conversation",
                session.conversation_id,
                "-p",
                content,
                "--dangerously-skip-permissions",
                "--output-format",
                "stream-json",
            ]
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(session.worktree_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
                with session.lock:
                    session.active_proc = proc

                assistant_text_chunks: List[str] = []

                if proc.stdout:
                    for line in proc.stdout:
                        clean_line = line.strip()
                        if not clean_line:
                            continue
                        try:
                            parsed = json.loads(clean_line)
                            evt_type = parsed.get("event")

                            if evt_type == "step_update":
                                su = parsed.get("step_update", {})
                                step_type = su.get("step_type")
                                if step_type == "agent_response":
                                    delta = su.get("text_delta", "")
                                    if delta:
                                        assistant_text_chunks.append(delta)
                                        self._broadcast(session, {"type": "delta", "delta": delta})
                                elif step_type == "tool":
                                    tool_name = su.get("tool_name", "tool")
                                    params = su.get("tool_info", {}).get("parameters", {})
                                    path_param = params.get("Path", params.get("path", ""))
                                    summary = f"{tool_name} {path_param}".strip()
                                    self._broadcast(session, {"type": "tool", "tool": summary})

                            elif evt_type == "result":
                                res = parsed.get("result", {})
                                full_resp = res.get("response", "".join(assistant_text_chunks))
                                self._broadcast(session, {"type": "result", "response": full_resp})

                        except Exception:
                            continue

                proc.wait()

                final_text = "".join(assistant_text_chunks).strip()
                if final_text:
                    with session.lock:
                        session.messages.append(ChatMessageResponse(role="assistant", content=final_text, timestamp=utc_now()))
                        session.updated_at = utc_now()

                # Check if NEW_ISSUE.md was created in the worktree
                new_issue_file = session.worktree_path / "NEW_ISSUE.md"
                if new_issue_file.is_file():
                    try:
                        content_md = new_issue_file.read_text(encoding="utf-8").strip()
                        title, body = parse_generated_issue(content_md)
                        draft = DraftIssue(title=title, body=body)
                        with session.lock:
                            session.draft_issue = draft
                        self._broadcast(session, {"type": "draft_issue", "draft": {"title": title, "body": body}})
                    except Exception as parse_exc:
                        logger.warning("Could not parse NEW_ISSUE.md: %s", parse_exc)

            except Exception as exc:
                logger.exception("Error executing turn for chat session %s: %s", session_id, exc)
                self._broadcast(session, {"type": "error", "error": str(exc)})
            finally:
                with session.lock:
                    session.active_proc = None
                self._broadcast(session, {"type": "done"})

        thread = threading.Thread(target=_turn_worker, daemon=True, name=f"chat-turn-{session_id}")
        thread.start()

    def terminate_session(self, db: Session, session_id: str) -> ChatSessionState:
        """Immediately terminate active process, clean up worktree, and mark TERMINATED."""
        session = self.get_session(session_id)
        project = projects_repo.get_by_id(db, session.project_id)
        repo_dir = Path(project.path) if project else None

        logger.info("Terminating chat formulation session %s immediately...", session_id)

        # 1. Kill subprocess
        with session.lock:
            if session.active_proc:
                try:
                    session.active_proc.terminate()
                    session.active_proc.kill()
                except Exception:
                    pass
                session.active_proc = None
            session.status = "TERMINATED"
            session.updated_at = utc_now()

        # 2. Cleanup scratch worktree
        if repo_dir:
            try:
                cleanup_worktree(
                    worktree_name=session.worktree_name,
                    branch_name=session.branch_name,
                    force=True,
                    repo_dir=repo_dir,
                )
            except Exception as exc:
                logger.warning("Worktree cleanup failed during termination of %s: %s", session_id, exc)

        self._broadcast(session, {"type": "terminated"})
        return session

    def create_and_run(self, db: Session, session_id: str, request: CreateAndRunRequest) -> CreateAndRunResponse:
        """Create GitHub issue from the chat draft and hand off to autonomous runner."""
        session = self.get_session(session_id)
        project = projects_repo.get_by_id(db, session.project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated project not found.")

        # 1. Create GitHub issue
        logger.info("Creating GitHub issue '%s' from chat session %s...", request.title, session_id)
        issue_detail = issues_service.create_issue_for_project(
            project,
            IssueCreateRequest(title=request.title, body=request.body),
        )

        # 2. Clean up scratch worktree & terminate chat session
        self.terminate_session(db, session_id)
        with session.lock:
            session.status = "CONVERTED"

        # 3. Start autonomous run for the created issue
        logger.info("Starting autonomous run for Issue #%s...", issue_detail.number)
        run_record = runs_service.start_run(
            db,
            RunCreateRequest(
                project_id=project.id,
                target_type="issue",
                target_id=str(issue_detail.number),
                auto_approve=request.auto_approve,
                engine=request.engine,
            ),
        )

        return CreateAndRunResponse(
            session_id=session_id,
            issue_number=issue_detail.number,
            issue_url=issue_detail.url,
            run_id=run_record.id,
            message=f"Created Issue #{issue_detail.number} and launched autonomous sandbox runner.",
        )

    def register_subscriber(self, session_id: str) -> asyncio.Queue:
        session = self.get_session(session_id)
        queue: asyncio.Queue = asyncio.Queue()
        with session.lock:
            session.subscribers.append(queue)
        return queue

    def remove_subscriber(self, session_id: str, queue: asyncio.Queue) -> None:
        try:
            session = self.get_session(session_id)
            with session.lock:
                if queue in session.subscribers:
                    session.subscribers.remove(queue)
        except Exception:
            pass

    def _broadcast(self, session: ChatSessionState, event: Dict[str, Any]) -> None:
        with session.lock:
            subs = list(session.subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except Exception:
                pass


chat_manager = ChatSessionManager()
