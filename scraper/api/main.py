"""
FastAPI Application Main Module

This module creates and configures the FastAPI application for the Async Scraper API.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from scraper.core.config import get_config
from scraper.core.logger import get_logger
from scraper.api.routes import health
from scraper.api.middleware.auth import AuthMiddleware
from scraper.api.middleware.rate_limit import RateLimitMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    config = get_config()
    
    logger.info("Starting Async Scraper API", version=app.version)
    
    # Startup logic
    try:
        # Initialize database connections, caches, etc.
        logger.info("API startup completed successfully")
        yield
    except Exception as e:
        logger.error("Failed to start API", error=str(e))
        raise
    finally:
        # Cleanup logic
        logger.info("Shutting down Async Scraper API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_config()
    
    app = FastAPI(
        title="Async Scraper API",
        description="High-performance, async-first web scraping framework API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Global exception handler."""
        logger.error(
            "Unhandled exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
            },
        )

    # Include routers
    app.include_router(health.router, prefix="/api/v1")

    return app


# Create the application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    config = get_config()
    
    uvicorn.run(
        "scraper.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.debug,
        log_level="debug" if config.debug else "info",
    )