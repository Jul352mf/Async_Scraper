"""System administration API endpoints."""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ....core.logger import get_logger
from ....core.monitoring import metrics_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/system", tags=["admin", "system"])


class SystemInfoResponse(BaseModel):
    """System information response model."""
    
    service_name: str
    version: str
    environment: str
    uptime_seconds: float
    build_info: Dict[str, str]


@router.get("/info", response_model=SystemInfoResponse)
async def get_system_info() -> SystemInfoResponse:
    """Get basic system information."""
    import time
    import os
    import platform
    from ....core.config import get_config
    
    config = get_config()
    
    # Calculate uptime (approximate)
    start_time_metric = metrics_manager.get_gauge("app_start_time")
    try:
        # Get the actual value from the metric
        start_time = start_time_metric._value._value if hasattr(start_time_metric, '_value') else time.time()
        uptime = time.time() - start_time
    except:
        uptime = 0.0
    
    return SystemInfoResponse(
        service_name="async-scraper",
        version="0.1.0",
        environment=os.getenv("ENVIRONMENT", "development"),
        uptime_seconds=uptime,
        build_info={
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture()[0],
            "hostname": platform.node(),
        }
    )


@router.get("/config")
async def get_system_config() -> Dict[str, Any]:
    """Get system configuration (sanitized)."""
    try:
        from ....core.config import get_config
        
        config = get_config()
        
        # Return sanitized config (remove sensitive data)
        return {
            "database": {
                "use_sqlite": config.database.use_sqlite,
                "auto_migrate": config.database.auto_migrate,
                "pool_size": config.database.pool_size,
                "max_overflow": config.database.max_overflow,
                # Don't include connection details or passwords
            },
            "queue": {
                "use_redis": config.queue.use_redis,
                "max_workers": config.queue.max_workers,
                "max_retries": config.queue.max_retries,
                "retry_delay": config.queue.retry_delay,
                # Don't include Redis URL
            },
            "scraping": {
                "timeout": config.scraping.timeout,
                "max_concurrent": config.scraping.max_concurrent,
                "rate_limit_per_second": config.scraping.rate_limit_per_second,
                "user_agent": config.scraping.user_agent,
            },
            "browser": {
                "max_browsers": config.browser.max_browsers,
                "max_contexts_per_browser": config.browser.max_contexts_per_browser,
                "default_browser": config.browser.default_browser,
                "headless": config.browser.headless,
                "viewport_width": config.browser.viewport_width,
                "viewport_height": config.browser.viewport_height,
                "timeout": config.browser.timeout,
            },
            "api": {
                "host": config.api.host,
                "port": config.api.port,
                "cors_enabled": config.api.cors_enabled,
                "rate_limit_requests": config.api.rate_limit_requests,
                "rate_limit_window": config.api.rate_limit_window,
            },
        }
        
    except Exception as e:
        logger.error("Failed to get system config", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get system config")


@router.get("/logs")
async def get_system_logs(
    level: Optional[str] = Query(None, description="Log level filter"),
    limit: int = Query(100, ge=1, le=1000, description="Number of logs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
) -> Dict[str, Any]:
    """Get system logs."""
    try:
        # This is a placeholder - in a real system you'd query your log storage
        # For now, return recent logs from the database if available
        from ....database import get_database_manager
        
        db = get_database_manager()
        
        # Build query
        query = "SELECT * FROM job_logs"
        params = {}
        
        if level:
            query += " WHERE level = :level"
            params["level"] = level
            
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        rows = await db.fetchall(query, params)
        logs = [dict(row) for row in rows]
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM job_logs"
        if level:
            count_query += " WHERE level = :level"
            count_params = {"level": level} if level else {}
        else:
            count_params = {}
            
        total_row = await db.fetchone(count_query, count_params)
        total = total_row["total"] if total_row else 0
        
        return {
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset,
            "level_filter": level
        }
        
    except Exception as e:
        logger.error("Failed to get system logs", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get system logs")


@router.post("/maintenance/gc")
async def run_garbage_collection() -> Dict[str, Any]:
    """Trigger garbage collection."""
    try:
        import gc
        
        # Get stats before
        before_objects = len(gc.get_objects())
        before_stats = gc.get_stats()
        
        # Run garbage collection
        collected = gc.collect()
        
        # Get stats after
        after_objects = len(gc.get_objects())
        after_stats = gc.get_stats()
        
        return {
            "message": "Garbage collection completed",
            "collected_objects": collected,
            "objects_before": before_objects,
            "objects_after": after_objects,
            "objects_freed": before_objects - after_objects,
            "stats_before": before_stats,
            "stats_after": after_stats
        }
        
    except Exception as e:
        logger.error("Failed to run garbage collection", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to run garbage collection")


@router.post("/maintenance/cleanup")
async def run_system_cleanup(
    cleanup_logs: bool = Query(True, description="Cleanup old logs"),
    cleanup_jobs: bool = Query(True, description="Cleanup old jobs"),
    retention_days: int = Query(30, ge=1, le=365, description="Retention period in days")
) -> Dict[str, Any]:
    """Run system-wide cleanup."""
    try:
        from datetime import datetime, timedelta
        from ....database import get_database_manager
        
        db = get_database_manager()
        cleanup_stats = {}
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_date.isoformat()
        
        if cleanup_logs:
            # Cleanup old logs
            result = await db.execute(
                "DELETE FROM job_logs WHERE created_at < ?",
                [cutoff_timestamp]
            )
            cleanup_stats["logs_deleted"] = getattr(result, 'rowcount', 0)
            
        if cleanup_jobs:
            # Cleanup old completed/failed jobs
            result = await db.execute(
                "DELETE FROM jobs WHERE status IN ('completed', 'failed') AND completed_at < ?",
                [cutoff_timestamp]
            )
            cleanup_stats["jobs_deleted"] = getattr(result, 'rowcount', 0)
            
            # Cleanup orphaned job results
            result = await db.execute(
                "DELETE FROM job_results WHERE created_at < ? AND job_id NOT IN (SELECT id FROM jobs)",
                [cutoff_timestamp]
            )
            cleanup_stats["results_deleted"] = getattr(result, 'rowcount', 0)
            
        # Record metrics
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "system_cleanup", "status": "success"}
        )
        
        return {
            "message": "System cleanup completed",
            "retention_days": retention_days,
            "cutoff_date": cutoff_timestamp,
            "stats": cleanup_stats
        }
        
    except Exception as e:
        logger.error("Failed to run system cleanup", error=str(e))
        
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "system_cleanup", "status": "error"}
        )
        
        raise HTTPException(status_code=500, detail="Failed to run system cleanup")


@router.get("/dependencies")
async def get_system_dependencies() -> Dict[str, Any]:
    """Get system dependencies and their status."""
    try:
        dependencies = {}
        
        # Check database
        try:
            from ....database import get_database_manager
            db = get_database_manager()
            await db.execute("SELECT 1")
            dependencies["database"] = {
                "status": "healthy",
                "type": "sqlite" if db.config.database.use_sqlite else "postgresql"
            }
        except Exception as e:
            dependencies["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            
        # Check queue system
        try:
            from ....queue import get_queue_manager
            queue_manager = get_queue_manager()
            stats = await queue_manager.get_queue_stats()
            dependencies["queue"] = {
                "status": "healthy",
                "type": "redis" if hasattr(queue_manager, 'redis_client') else "in_memory",
                "stats": stats
            }
        except Exception as e:
            dependencies["queue"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            
        # Check proxy manager
        try:
            from ....core.proxy import get_proxy_manager
            proxy_manager = get_proxy_manager()
            stats = await proxy_manager.get_stats()
            dependencies["proxy_manager"] = {
                "status": "healthy",
                "stats": stats
            }
        except Exception as e:
            dependencies["proxy_manager"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            
        # Check browser manager
        try:
            from ....services.browser_manager import get_browser_manager
            browser_manager = get_browser_manager()
            dependencies["browser_manager"] = {
                "status": "healthy" if browser_manager else "unhealthy"
            }
        except Exception as e:
            dependencies["browser_manager"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": dependencies
        }
        
    except Exception as e:
        logger.error("Failed to get system dependencies", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get system dependencies")