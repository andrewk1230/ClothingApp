import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.ml.clip_model import load_clip
    from app.ml.yolo_model import load_yolo
    from scraper.scheduler import start_scheduler, stop_scheduler

    load_clip(settings.clip_model, settings.clip_pretrained)
    load_yolo(settings.yolo_weights_path)
    start_scheduler()

    logger.info("GrailSeeker API started")
    yield

    stop_scheduler()
    logger.info("GrailSeeker API shutting down")


def create_app() -> FastAPI:
    production = settings.environment == "production"

    app = FastAPI(
        title="GrailSeeker API",
        description="Visual search engine for second-hand clothing",
        version="0.1.0",
        lifespan=lifespan,
        # No public API surface documentation in production.
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Uniform JSON body with no exception detail; the traceback goes to
        # the server log only.
        logger.error(
            "Unhandled error on %s %s", request.method, request.url.path,
            exc_info=exc,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    from app.routers import auth, history, listings, rate_limit, saved, search

    app.include_router(search.router)
    app.include_router(listings.router)
    app.include_router(saved.router)
    app.include_router(history.router)
    app.include_router(auth.router)
    app.include_router(rate_limit.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
