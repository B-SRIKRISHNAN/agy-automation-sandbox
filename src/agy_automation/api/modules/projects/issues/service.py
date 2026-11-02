"""Service layer for Project Issues operations."""

from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException, status

from agy_automation.api.modules.projects.issues.schemas import (
    IssueCreateRequest,
    IssueDetail,
    IssueListItem,
    IssueListResponse,
    IssueProviderStatusResponse,
)
from agy_automation.api.modules.projects.models import Project
from agy_automation.core.create_issue import create_github_issue
from agy_automation.core.exceptions import IssueCreationError, IssueNotFoundError
from agy_automation.core.fetch_issue import (
    build_markdown_context,
    fetch_issue_payload,
    get_issue_provider_status,
    list_github_issues,
)
from agy_automation.core.logging import get_logger

logger = get_logger("agy_automation.api.projects.issues.service")


def get_provider_status_for_project(project: Project) -> IssueProviderStatusResponse:
    """Check whether GitHub issues can be fetched or created for the given project."""
    repo_path = Path(project.path)
    res = get_issue_provider_status(repo_dir=repo_path)
    return IssueProviderStatusResponse(
        available=res["available"],
        gh_installed=res["gh_installed"],
        authenticated=res["authenticated"],
        has_remote=res["has_remote"],
        remote_url=res.get("remote_url") or project.git_remote or "",
        reason=res.get("reason"),
    )


def list_issues_for_project(
    project: Project,
    state: str = "open",
    limit: int = 30,
) -> IssueListResponse:
    """Retrieve summarized list of issues for a project."""
    repo_path = Path(project.path)
    raw_issues = list_github_issues(repo_dir=repo_path, state=state, limit=limit)

    items: List[IssueListItem] = []
    for item in raw_issues:
        num = item.get("number", 0)
        title = item.get("title", "")
        st = item.get("state", "OPEN")

        author_raw = item.get("author") or {}
        author = author_raw.get("login", "Unknown") if isinstance(author_raw, dict) else str(author_raw)

        labels_raw = item.get("labels") or []
        labels: List[str] = []
        if isinstance(labels_raw, list):
            for l in labels_raw:
                if isinstance(l, dict) and l.get("name"):
                    labels.append(l["name"])
                elif isinstance(l, str):
                    labels.append(l)

        items.append(
            IssueListItem(
                number=num,
                title=title,
                state=st,
                author=author,
                labels=labels,
                updated_at=item.get("updatedAt", ""),
                url=item.get("url", ""),
            )
        )

    return IssueListResponse(issues=items, total=len(items), state=state)


def get_issue_detail_for_project(project: Project, issue_number: int) -> IssueDetail:
    """Retrieve full issue payload, comments, and formatted context markdown."""
    repo_path = Path(project.path)
    try:
        data = fetch_issue_payload(issue_number, repo_dir=repo_path)
    except IssueNotFoundError as exc:
        logger.warning("Issue #%d not found in %s: %s", issue_number, project.path, exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue #{issue_number} not found or inaccessible in project '{project.name}'",
        ) from exc
    except Exception as exc:
        logger.error("Failed to fetch issue #%d in %s: %s", issue_number, project.path, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch issue #{issue_number}: {exc}",
        ) from exc

    context_md = build_markdown_context(data)

    author_raw = data.get("author") or {}
    author = author_raw.get("login", "Unknown") if isinstance(author_raw, dict) else str(author_raw)

    labels_raw = data.get("labels") or []
    labels: List[str] = []
    if isinstance(labels_raw, list):
        for l in labels_raw:
            if isinstance(l, dict) and l.get("name"):
                labels.append(l["name"])
            elif isinstance(l, str):
                labels.append(l)

    comments = data.get("comments") or []
    comments_count = len(comments) if isinstance(comments, list) else 0

    return IssueDetail(
        number=data.get("number", issue_number),
        title=data.get("title", ""),
        body=data.get("body", "") or "",
        state=data.get("state", "OPEN"),
        author=author,
        labels=labels,
        url=data.get("url", ""),
        comments_count=comments_count,
        context_markdown=context_md,
    )


def create_issue_for_project(project: Project, payload: IssueCreateRequest) -> IssueDetail:
    """Publish a new issue to GitHub in the project's repository."""
    repo_path = Path(project.path)
    try:
        created = create_github_issue(
            title=payload.title,
            body=payload.body,
            labels=payload.labels,
            repo_dir=repo_path,
        )
    except IssueCreationError as exc:
        logger.error("Failed to create GitHub issue in %s: %s", project.path, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"GitHub issue creation failed: {exc}",
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error creating issue: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error creating issue: {exc}",
        ) from exc

    issue_number = created.get("number")
    if issue_number:
        try:
            return get_issue_detail_for_project(project, issue_number)
        except Exception:
            pass

    return IssueDetail(
        number=issue_number or 0,
        title=created["title"],
        body=created["body"],
        state="OPEN",
        url=created.get("url", ""),
        labels=created.get("labels", []),
    )
