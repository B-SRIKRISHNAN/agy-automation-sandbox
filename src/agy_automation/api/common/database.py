"""Database engine, session management, and migration execution for API."""

import sqlite3
from pathlib import Path
from typing import Generator, Optional

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from agy_automation.api.config import DATABASE_URL
from agy_automation.core.logging import get_logger

logger = get_logger("agy_automation.api.db")


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 ORM models."""
    pass


def create_db_engine(db_url: str) -> Engine:
    """Create and configure a SQLAlchemy engine with dialect-specific options."""
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    eng = create_engine(db_url, connect_args=connect_args)

    if db_url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return eng


engine = create_db_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and safely closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_db_migrations(db_url: Optional[str] = None) -> None:
    """Execute Alembic migrations programmatically up to 'head'."""
    url = db_url or DATABASE_URL
    api_dir = Path(__file__).resolve().parent.parent
    migrations_dir = api_dir / "migrations"
    ini_path = migrations_dir / "alembic.ini"

    logger.info("Applying database migrations against: %s", url)
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("script_location", str(migrations_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(alembic_cfg, "head")
    logger.info("Database migrations applied successfully.")
