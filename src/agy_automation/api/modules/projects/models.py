"""SQLAlchemy 2.0 ORM model for Projects."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from agy_automation.api.common.database import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Project(Base):
    """SQLAlchemy 2.0 model representing a registered local Git project."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    git_remote: Mapped[str] = mapped_column(Text, default="", nullable=False)
    git_branch: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    instructions_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
