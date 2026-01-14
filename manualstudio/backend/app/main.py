"""FastAPI application entry point."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import ManualStudioError
from app.api.routes import router as api_router
from app.api.views import router as views_router

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Create app
app = FastAPI(
    title="ManualStudio",
    description="画面録画から操作マニュアルを自動生成するWebアプリ",
    version="1.0.0",
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
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    settings = get_settings()
    logger.info("ManualStudio starting up")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Transcription Provider: {settings.transcribe_provider}")
    logger.info(f"Max Video Duration: {settings.max_video_minutes} minutes")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("ManualStudio shutting down")
