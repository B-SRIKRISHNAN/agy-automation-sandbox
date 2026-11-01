"""Core engine package for agy-automation.

Contains headless domain logic, configuration, context, and exceptions.
Free from terminal I/O (no direct input() or sys.exit()).
"""

from .context import PipelineContext
from .exceptions import (
    AutomationError,
    BranchNotFoundError,
    ComposeExecutionError,
    ConfigurationError,
    ContainerEngineNotFoundError,
    ContainerError,
    DirtyWorkspaceError,
    GitError,
    GitHubCliNotFoundError,
    GitHubError,
    IssueCreationError,
    IssueNotFoundError,
    MergeConflictError,
    SandboxExecutionError,
    UserCancelledError,
    WorktreeConflictError,
)
from .logging import RunSession, get_logger

__all__ = [
    "AutomationError",
    "BranchNotFoundError",
    "ComposeExecutionError",
    "ConfigurationError",
    "ContainerEngineNotFoundError",
    "ContainerError",
    "DirtyWorkspaceError",
    "GitError",
    "GitHubCliNotFoundError",
    "GitHubError",
    "IssueCreationError",
    "IssueNotFoundError",
    "MergeConflictError",
    "PipelineContext",
    "RunSession",
    "SandboxExecutionError",
    "UserCancelledError",
    "WorktreeConflictError",
    "get_logger",
]
