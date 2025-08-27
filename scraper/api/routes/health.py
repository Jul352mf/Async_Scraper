"""
Health Check API Routes

Provides health check endpoints for monitoring system status.
"""

import asyncio
import time
from typing import Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from scraper.core.logger import get_logger
from scraper.database import get_database_manager
from scraper.api.persistent_job_manager import get_persistent_job_manager

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=Dict[str, Any])
async def health_check() -> JSONResponse:
    """
    Basic health check endpoint.
    
    Returns:
        JSON response with health status and timestamp
    """
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "service": "async-scraper-api"
    }
    
    logger.debug("Health check requested")
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=health_data
    )


@router.get("/health/detailed", response_model=Dict[str, Any])
async def detailed_health_check() -> JSONResponse:
    """
    Detailed health check with system information.
    
    Returns:
        JSON response with detailed health information
    """
    start_time = time.time()
    overall_status = "healthy"
    checks = {}
    
    # Database health check
    try:
        db = get_database_manager()
        db_start = time.time()
        db_healthy = await db.health_check()
        db_response_time = (time.time() - db_start) * 1000
        
        checks["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "response_time": round(db_response_time, 2),
        }
        
        if not db_healthy:
            overall_status = "degraded"
            
    except Exception as e:
        checks["database"] = {
            "status": "error",
            "response_time": None,
            "error": str(e),
        }
        overall_status = "unhealthy"
    
    # Job queue health check
    try:
        job_manager = get_persistent_job_manager()
        queue_stats = await job_manager.queue.get_queue_stats()
        
        queue_healthy = queue_stats.get("running", False)
        redis_connected = queue_stats.get("redis_connected", True)  # True for in-memory queue
        
        checks["queue"] = {
            "status": "healthy" if queue_healthy else "unhealthy",
            "backend": "redis" if hasattr(job_manager.queue, 'redis_url') else "in-memory",
            "redis_connected": redis_connected,
            "total_jobs": queue_stats.get("total_jobs", 0),
            "pending": queue_stats.get("pending", 0),
            "processing": queue_stats.get("processing", 0),
            "completed": queue_stats.get("completed", 0),
            "failed": queue_stats.get("failed", 0),
            "active_workers": queue_stats.get("active_workers", 0),
        }
        
        if not queue_healthy or not redis_connected:
            overall_status = "degraded"
            
    except Exception as e:
        checks["queue"] = {
            "status": "error",
            "error": str(e),
        }
        overall_status = "unhealthy"
    
    # Redis health check (if using Redis queue)
    try:
        job_manager = get_persistent_job_manager()
        if hasattr(job_manager.queue, 'redis') and job_manager.queue.redis:
            redis_start = time.time()
            redis_healthy = await job_manager.queue.health_check()
            redis_response_time = (time.time() - redis_start) * 1000
            
            checks["redis"] = {
                "status": "healthy" if redis_healthy else "unhealthy",
                "response_time": round(redis_response_time, 2),
            }
            
            if not redis_healthy:
                overall_status = "degraded"
        else:
            checks["redis"] = {
                "status": "not_configured",
                "response_time": None,
                "note": "Using in-memory queue"
            }
            
    except Exception as e:
        checks["redis"] = {
            "status": "error",
            "response_time": None,
            "error": str(e),
        }
        overall_status = "unhealthy"
    
    # Cache health check (basic)
    checks["cache"] = {
        "status": "healthy",
        "hit_ratio": 0.0,  # TODO: Implement cache metrics
    }
    
    total_response_time = (time.time() - start_time) * 1000
    
    health_data = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "service": "async-scraper-api",
        "checks": checks,
        "metrics": {
            "health_check_duration_ms": round(total_response_time, 2),
            "uptime": "< 1m",  # TODO: Track actual uptime
            "active_connections": 0,  # TODO: Track connections
            "total_requests": 0,  # TODO: Track requests
            "average_response_time": 0.0  # TODO: Track response times
        }
    }
    
    logger.info("Detailed health check requested", 
                status=overall_status, 
                duration_ms=round(total_response_time, 2))
    
    # Return appropriate status code based on health
    status_code = status.HTTP_200_OK
    if overall_status == "degraded":
        status_code = status.HTTP_200_OK  # Still OK, but with warnings
    elif overall_status == "unhealthy":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content=health_data
    )