"""Pipeline context definition for agy-automation.

Encapsulates all runtime execution parameters, eliminating parameter drilling
and providing a consistent context across CLI, API, and TUI frontends.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class PipelineContext:
    """Strongly typed execution context for an automation run."""

    target_repo: Path
    target_type: str = "issue"  # "issue" | "session" | "new_issue"
    target_id: str = "42"       # Issue number or session name
    base_branch: str = "master"
    worktree_name: str = ""
    branch_name: str = ""
    worktree_path: Optional[Path] = None
    engine: str = "auto"
    interactive: bool = False
    auto_approve: bool = False
    dry_run: bool = False
    build: bool = False
    new_issue_prompt: Optional[str] = None
    instructions_file: Optional[Path] = None
    session_logger: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.target_repo, str):
            self.target_repo = Path(self.target_repo).resolve()
        else:
            self.target_repo = self.target_repo.resolve()

        if not self.worktree_name or not self.branch_name:
            self.derive_names()

        if self.worktree_path is None and self.worktree_name:
            self.worktree_path = self.target_repo / ".worktrees" / self.worktree_name

    def derive_names(self) -> None:
        """Derive standard worktree and branch names based on target_type and target_id."""
        clean_id = str(self.target_id).strip().lstrip("#")
        if self.target_type == "session":
            # Sanitize session name
            sanitized = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in clean_id).strip("-")
            clean_id = sanitized or "unnamed"
            if not self.worktree_name:
                self.worktree_name = f"worktree-{clean_id}"
            if not self.branch_name:
                self.branch_name = f"session/{clean_id}"
        elif self.target_type in ("issue", "new_issue"):
            if not self.worktree_name:
                self.worktree_name = f"worktree-issue-{clean_id}"
            if not self.branch_name:
                self.branch_name = f"issue-{clean_id}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to a serializable dictionary for logging and API serialization."""
        return {
            "target_repo": str(self.target_repo),
            "target_type": self.target_type,
            "target_id": self.target_id,
            "base_branch": self.base_branch,
            "worktree_name": self.worktree_name,
            "branch_name": self.branch_name,
            "worktree_path": str(self.worktree_path) if self.worktree_path else None,
            "engine": self.engine,
            "interactive": self.interactive,
            "auto_approve": self.auto_approve,
            "dry_run": self.dry_run,
            "build": self.build,
            "new_issue_prompt": self.new_issue_prompt,
            "instructions_file": str(self.instructions_file) if self.instructions_file else None,
            "metadata": self.metadata,
        }
