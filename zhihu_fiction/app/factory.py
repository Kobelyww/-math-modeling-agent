"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..workspace_routes import create_workspace_router
from .dependencies import AppDependencies
from .routes import costs, drama_video, health, ip_memory, pipeline, projects, static, stories, tasks
from .security import install_security
from .services.drama_video_recovery import recover_video_jobs_after_restart
from .state import AppState

logger = logging.getLogger("zhihu_fiction.server")


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info(
            "%s %s - %d (%.2fs)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    deps = getattr(request.app.state, "dependencies", None)
    web_settings = getattr(deps, "web_settings", None)
    expose = bool(getattr(web_settings, "expose_error_details", True))
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc) if expose else "Internal Server Error",
            "path": str(request.url.path),
        },
    )


def create_app(
    dependencies: AppDependencies | None = None,
    state: AppState | None = None,
) -> FastAPI:
    """Build the Zhihu Fiction FastAPI application."""

    deps = dependencies or AppDependencies()
    runtime = state or AppState()

    def recover_video_jobs_on_startup() -> None:
        result = recover_video_jobs_after_restart(deps.workspace_repo)
        deps.video_job_recovery = result
        if result.get("refresh_queued") or result.get("failed"):
            logger.info("Recovered video jobs after restart: %s", result)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        recover_video_jobs_on_startup()
        yield

    app = FastAPI(title="Zhihu Fiction Studio", version="1.0", lifespan=lifespan)
    app.state.dependencies = deps
    app.state.runtime = runtime

    app.add_middleware(
        CORSMiddleware,
        allow_origins=deps.web_settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(TimingMiddleware)
    install_security(app, deps.web_settings)
    app.add_exception_handler(Exception, global_exception_handler)

    app.include_router(health.router)
    app.include_router(static.router)
    app.include_router(stories.router)
    app.include_router(projects.router)
    app.include_router(ip_memory.router)
    app.include_router(costs.router)
    app.include_router(tasks.router)
    app.include_router(pipeline.router)
    app.include_router(drama_video.router)
    create_exporter = getattr(deps, "create_exporter", None)
    if create_exporter is None:
        create_exporter = AppDependencies.create_exporter.__get__(deps, type(deps))

    app.include_router(
        create_workspace_router(
            deps.workspace_service,
            deps.workspace_queue,
            create_exporter,
        )
    )
    return app
