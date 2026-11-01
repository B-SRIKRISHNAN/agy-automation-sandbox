"""Dual-track logging and telemetry engine for agy-automation.

Combines:
1. Standard Python diagnostic logging (logging.getLogger("agy_automation"))
2. RunSession structured run telemetry (metadata.json and events.jsonl)
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_LOGGER_NAME = "agy_automation"


def get_logger(name: str = DEFAULT_LOGGER_NAME) -> logging.Logger:
    """Return a scoped logger for agy-automation core and CLI modules."""
    return logging.getLogger(name)


def configure_logging(level: int = logging.INFO, verbose: bool = False) -> None:
    """Configure basic root/package logging handler and format."""
    effective_level = logging.DEBUG if verbose else level
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger = logging.getLogger(DEFAULT_LOGGER_NAME)
    logger.setLevel(effective_level)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(handler)


def get_default_runs_dir() -> Path:
    """Resolve OS-agnostic runs directory under user home or AGY_RUNS_DIR env var."""
    override = os.environ.get("AGY_RUNS_DIR")
    if override:
        path = Path(override).expanduser().resolve()
    else:
        path = (Path.home() / ".agy-automation" / "runs").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename_component(name: str) -> str:
    """Sanitize a string for safe use in file/directory paths across OSes."""
    s = re.sub(r"[^\w\-\.]+", "_", name.strip())
    s = re.sub(r"_+", "_", s).strip("_.")
    return s or "run"


def generate_run_id(project_name: str, target: str) -> str:
    """Generate a unique, chronological, filesystem-safe run identifier."""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_proj = sanitize_filename_component(project_name)
    safe_target = sanitize_filename_component(str(target))
    return f"{now_str}_{safe_proj}_{safe_target}"


class RunSession:
    """Manages the full lifecycle log directory, metadata, and NDJSON events for a run."""

    def __init__(
        self,
        project_name: str,
        target: str,
        base_runs_dir: Optional[Path] = None,
        run_id: Optional[str] = None,
    ):
        self.base_runs_dir = base_runs_dir or get_default_runs_dir()
        self.run_id = run_id or generate_run_id(project_name, target)
        self.run_dir = self.base_runs_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.run_dir / "metadata.json"
        self.events_file = self.run_dir / "events.jsonl"

        self._events_handle = open(self.events_file, "a", encoding="utf-8")

        self.started_at = datetime.now(timezone.utc)
        self.status = "RUNNING"
        self.metadata: Dict[str, Any] = {
            "run_id": self.run_id,
            "status": self.status,
            "target_project": {
                "name": project_name,
                "repo_path": "",
                "git_remote": "",
                "start_commit": "",
            },
            "context": {
                "mode": "issue" if str(target).isdigit() else "session",
                "target": target,
                "issue_number": int(target) if str(target).isdigit() else None,
                "issue_title": "",
                "issue_url": "",
                "session_name": None if str(target).isdigit() else target,
            },
            "git": {
                "base_branch": "",
                "branch_name": "",
                "worktree_name": "",
                "worktree_path": "",
            },
            "environment": {
                "engine": "",
                "container_name": "",
                "host_os": sys.platform,
                "python_version": sys.version.split()[0],
            },
            "timing": {
                "started_at": self.started_at.isoformat(),
                "ended_at": None,
                "duration_seconds": None,
            },
            "results": {
                "merged": False,
                "pushed": False,
                "final_commit_hash": None,
                "final_commit_subject": None,
            },
            "metrics": {
                "total_turns": 0,
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "thinking_tokens": 0,
                "tool_calls": {},
            },
            "log_files": {
                "run_dir": str(self.run_dir),
                "metadata": str(self.metadata_file),
                "events": str(self.events_file),
            },
        }
        self._write_metadata()

    def update_context(
        self,
        repo_path: Optional[str] = None,
        git_remote: Optional[str] = None,
        start_commit: Optional[str] = None,
        base_branch: Optional[str] = None,
        branch_name: Optional[str] = None,
        worktree_name: Optional[str] = None,
        worktree_path: Optional[str] = None,
        engine: Optional[str] = None,
        container_name: Optional[str] = None,
        issue_title: Optional[str] = None,
        issue_url: Optional[str] = None,
    ) -> None:
        """Update metadata context and persist immediately."""
        if repo_path:
            self.metadata["target_project"]["repo_path"] = str(repo_path)
        if git_remote:
            self.metadata["target_project"]["git_remote"] = str(git_remote)
        if start_commit:
            self.metadata["target_project"]["start_commit"] = str(start_commit)
        if base_branch:
            self.metadata["git"]["base_branch"] = str(base_branch)
        if branch_name:
            self.metadata["git"]["branch_name"] = str(branch_name)
        if worktree_name:
            self.metadata["git"]["worktree_name"] = str(worktree_name)
        if worktree_path:
            self.metadata["git"]["worktree_path"] = str(worktree_path)
        if engine:
            self.metadata["environment"]["engine"] = str(engine)
        if container_name:
            self.metadata["environment"]["container_name"] = str(container_name)
        if issue_title:
            self.metadata["context"]["issue_title"] = str(issue_title)
        if issue_url:
            self.metadata["context"]["issue_url"] = str(issue_url)

        self._write_metadata()

    def log_event(
        self,
        source: str,
        phase: str,
        event_name: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a structured, chronological event to events.jsonl."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "source": source,
            "phase": phase,
            "event": event_name,
            "data": payload or {},
        }
        self._events_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._events_handle.flush()

    def log_raw_agent_event(self, raw_json_line: str) -> Optional[Dict[str, Any]]:
        """Parse native agy stream-json line, persist to log, and track token/tool metrics."""
        line_clean = raw_json_line.strip()
        if not line_clean:
            return None

        try:
            parsed = json.loads(line_clean)
        except Exception:
            self.log_event("agent", "sandbox", "stdout", {"raw": line_clean})
            return None

        envelope = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "source": "agent",
            "phase": "sandbox",
            "event": parsed.get("event", "stream_event"),
            "data": parsed,
        }
        self._events_handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
        self._events_handle.flush()

        evt_type = parsed.get("event")
        if evt_type == "step_update":
            su = parsed.get("step_update") or {}
            step_type = su.get("step_type")

            if step_type == "tool":
                tool_name = su.get("tool_name", "unknown")
                state = su.get("state")
                if state == "ACTIVE":
                    t_counts = self.metadata["metrics"]["tool_calls"]
                    t_counts[tool_name] = t_counts.get(tool_name, 0) + 1

            usage = su.get("usage")
            if isinstance(usage, dict):
                self._accumulate_tokens(usage)

        elif evt_type == "result":
            res = parsed.get("result") or {}
            usage = res.get("usage")
            if isinstance(usage, dict):
                self.metadata["metrics"]["total_tokens"] = usage.get("total_tokens", self.metadata["metrics"]["total_tokens"])
                self.metadata["metrics"]["input_tokens"] = usage.get("input_tokens", self.metadata["metrics"]["input_tokens"])
                self.metadata["metrics"]["output_tokens"] = usage.get("output_tokens", self.metadata["metrics"]["output_tokens"])
                self.metadata["metrics"]["thinking_tokens"] = usage.get("thinking_tokens", self.metadata["metrics"]["thinking_tokens"])
            turns = res.get("num_turns")
            if isinstance(turns, int):
                self.metadata["metrics"]["total_turns"] = turns

        self._write_metadata()
        return parsed

    def _accumulate_tokens(self, usage: Dict[str, Any]) -> None:
        """Accumulate token counts from a step usage object."""
        m = self.metadata["metrics"]
        m["input_tokens"] += usage.get("input_tokens", 0)
        m["output_tokens"] += usage.get("output_tokens", 0)
        m["thinking_tokens"] += usage.get("thinking_tokens", 0)
        m["total_tokens"] += usage.get("total_tokens", 0)

    def finish(
        self,
        status: str,
        merged: bool = False,
        pushed: bool = False,
        final_commit_hash: Optional[str] = None,
        final_commit_subject: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Finalize the run session, record outcome, and flush all files."""
        ended_at = datetime.now(timezone.utc)
        duration = (ended_at - self.started_at).total_seconds()

        self.status = status
        self.metadata["status"] = status
        self.metadata["timing"]["ended_at"] = ended_at.isoformat()
        self.metadata["timing"]["duration_seconds"] = round(duration, 3)

        self.metadata["results"]["merged"] = merged
        self.metadata["results"]["pushed"] = pushed
        if final_commit_hash:
            self.metadata["results"]["final_commit_hash"] = final_commit_hash
        if final_commit_subject:
            self.metadata["results"]["final_commit_subject"] = final_commit_subject
        if error:
            self.metadata["error"] = error

        self.log_event("coordinator", "finish", "session_finished", {
            "status": status,
            "duration_seconds": round(duration, 3),
            "merged": merged,
            "pushed": pushed,
            "error": error,
        })

        self._write_metadata()
        self._events_handle.flush()
        self._events_handle.close()

    def _write_metadata(self) -> None:
        """Write metadata.json atomically using a temp file."""
        tmp_file = self.run_dir / "metadata.json.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
            tmp_file.replace(self.metadata_file)
        except Exception:
            pass
