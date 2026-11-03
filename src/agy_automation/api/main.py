"""Main FastAPI application factory and entrypoint for agy-automation API."""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from agy_automation.api.common.database import run_db_migrations
from agy_automation.api.modules.projects.router import router as projects_router
from agy_automation.api.modules.runs.router import router as runs_router
from agy_automation.core.logging import configure_logging, get_logger

logger = get_logger("agy_automation.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events."""
    configure_logging(level=logging.INFO)
    logger.info("Starting Antigravity Automation API...")

    if not os.environ.get("AGY_SKIP_MIGRATIONS"):
        try:
            run_db_migrations()
        except Exception as exc:
            logger.error("Failed to run startup database migrations: %s", exc)
            raise exc

    yield
    logger.info("Shutting down Antigravity Automation API...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Antigravity Automation API",
        description="REST API backend for autonomous issue resolution and project orchestration",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 1. Global CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Global Request Timing & Telemetry Middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        return response

    # 3. Root health check endpoint
    @app.get("/api/health", tags=["system"])
    def health_check():
        return {"status": "ok", "version": "1.0.0"}

    # 4. Mount Feature Routers
    app.include_router(projects_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")

    return app


app = create_app()
