"""Main FastAPI application factory and entrypoint for agy-automation API."""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from agy_automation.api.common.database import run_db_migrations
from agy_automation.api.modules.chat.router import router as chat_router
from agy_automation.api.modules.projects.router import router as projects_router
from agy_automation.api.modules.runs.router import router as runs_router
from agy_automation.api.modules.system.router import router as system_router
from agy_automation.core.logging import configure_logging, get_logger

logger = get_logger("agy_automation.api")


class SPAStaticFiles(StaticFiles):
    """Serve static files with client-side SPA fallback to index.html for unknown routes."""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
            if response.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            return response
        except HTTPException as ex:
            if ex.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise


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
    app.include_router(chat_router, prefix="/api")
    app.include_router(system_router, prefix="/api")

    # 5. Serve Mobile-First PWA (Vite dist) if built
    web_dist = Path(__file__).resolve().parent.parent.parent.parent / "web" / "dist"
    if web_dist.is_dir():
        app.mount("/", SPAStaticFiles(directory=str(web_dist), html=True), name="pwa")

    return app


app = create_app()
