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
from scraper.api.routes import health, scrape, jobs, websocket, proxy
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
        # Initialize database and run migrations
        if config.database.auto_migrate:
            from scraper.database import get_database_manager, run_migrations
            db_manager = get_database_manager()
            await run_migrations(db_manager)
            logger.info("Database migrations completed")
        
        # Initialize persistent job manager
        from scraper.api.persistent_job_manager import get_persistent_job_manager
        await get_persistent_job_manager()
        logger.info("Persistent job manager initialized")
        
        # Initialize proxy manager if enabled
        if config.proxy.enabled and config.proxy.proxy_urls:
            from scraper.core.proxy import ProxyManager
            from scraper.core.proxy.models import ProxyConfig as ProxyConfigModel
            from scraper.api.routes.proxy import set_proxy_manager
            
            proxy_config = ProxyConfigModel(**config.proxy.model_dump())
            proxy_manager = ProxyManager.from_urls(config.proxy.proxy_urls, proxy_config)
            await proxy_manager.initialize()
            set_proxy_manager(proxy_manager)
            logger.info("Proxy manager initialized", proxy_count=len(proxy_manager.list_proxies()))
        
        # Initialize browser manager if JavaScript support is enabled
        if config.browser.enabled:
            from scraper.services.browser_manager import get_browser_manager
            await get_browser_manager()
            logger.info("Browser manager initialized")
        
        logger.info("API startup completed successfully")
        yield
    except Exception as e:
        logger.error("Failed to start API", error=str(e))
        raise
    finally:
        # Cleanup logic
        from scraper.api.persistent_job_manager import _persistent_job_manager
        if _persistent_job_manager:
            await _persistent_job_manager.shutdown()
            logger.info("Persistent job manager cleaned up")
        
        if config.proxy.enabled:
            from scraper.api.routes.proxy import get_proxy_manager
            try:
                proxy_manager = get_proxy_manager()
                await proxy_manager.shutdown()
                logger.info("Proxy manager cleaned up")
            except Exception as e:
                logger.warning("Error cleaning up proxy manager", error=str(e))
        
        if config.browser.enabled:
            from scraper.services.browser_manager import cleanup_browser_manager
            await cleanup_browser_manager()
            logger.info("Browser manager cleaned up")
        
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
    app.include_router(health.router)
    app.include_router(scrape.router)
    app.include_router(jobs.router)
    app.include_router(websocket.router)
    app.include_router(proxy.router)

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