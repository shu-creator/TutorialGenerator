"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.api.views import router as views_router
from app.core.config import get_settings
from app.core.exceptions import ManualStudioError
from app.core.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    settings = get_settings()
    logger.info("ManualStudio starting up")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Transcription Provider: {settings.transcribe_provider}")
    logger.info(f"Max Video Duration: {settings.max_video_minutes} minutes")

    yield

    # Shutdown
    logger.info("ManualStudio shutting down")


# Create app
app = FastAPI(
    title="ManualStudio",
    description="画面録画から操作マニュアルを自動生成するWebアプリ",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(api_router)
app.include_router(views_router)

# Static files (if needed)
# app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(ManualStudioError)
async def manualstudio_exception_handler(request: Request, exc: ManualStudioError):
    """Handle ManualStudio exceptions."""
    logger.error(f"ManualStudioError: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.code,
            "message": exc.message,
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
