"""Domain exception hierarchy for agy-automation.

Provides strongly-typed domain errors to allow programmatic handling by
APIs, TUIs, and the CLI instead of catching generic RuntimeError.
"""

from typing import List, Optional


class AutomationError(RuntimeError):
    """Base exception for all agy-automation domain failures."""


# --- Git & Worktree Exceptions ---

class GitError(AutomationError):
    """Base exception for Git operations."""


class WorktreeConflictError(GitError):
    """Raised when a worktree directory or branch already exists."""


class DirtyWorkspaceError(GitError):
    """Raised when tracked files on the base branch have uncommitted modifications."""

    def __init__(self, dirty_files: Optional[List[str]] = None, message: str = ""):
        self.dirty_files = dirty_files or []
        count = len(self.dirty_files)
        default_msg = f"Working tree has uncommitted modifications in {count} file(s)." if count else "Working tree is dirty."
        super().__init__(message or default_msg)


class MergeConflictError(GitError):
    """Raised when Git merge encounters unresolved conflicts."""

    def __init__(self, conflict_files: Optional[List[str]] = None, message: str = ""):
        self.conflict_files = conflict_files or []
        count = len(self.conflict_files)
        default_msg = f"Merge encountered conflicts in {count} file(s)." if count else "Merge conflicts detected."
        super().__init__(message or default_msg)


class BranchNotFoundError(GitError):
    """Raised when an expected Git branch cannot be resolved."""


# --- Container & Sandbox Exceptions ---

class ContainerError(AutomationError):
    """Base exception for container engine and sandbox execution."""


class ContainerEngineNotFoundError(ContainerError):
    """Raised when neither Podman nor Docker is installed or active."""


class ComposeExecutionError(ContainerError):
    """Raised when a docker-compose or podman-compose command fails."""


class SandboxExecutionError(ContainerError):
    """Raised when the sandbox agent runner container exits with a non-zero code."""

    def __init__(self, returncode: int, message: str = ""):
        self.returncode = returncode
        super().__init__(message or f"Sandbox container exited with error code {returncode}.")


# --- GitHub Exceptions ---

class GitHubError(AutomationError):
    """Base exception for GitHub interactions."""


class GitHubCliNotFoundError(GitHubError):
    """Raised when gh CLI is not installed or not found in PATH."""


class IssueNotFoundError(GitHubError):
    """Raised when the requested issue is not found on GitHub."""


class IssueCreationError(GitHubError):
    """Raised when creating an issue via GitHub CLI fails."""


# --- Configuration & User Control Exceptions ---

class ConfigurationError(AutomationError):
    """Raised when configuration is invalid or missing."""


class UserCancelledError(AutomationError):
    """Raised when a user explicitly aborts or declines a prompt."""
