"""Monitoring and metrics API endpoints."""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from ....core.monitoring import metrics_manager, health_checker
from ....core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/monitoring", tags=["admin", "monitoring"])


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str
    timestamp: float
    checks: Dict[str, Any]
    summary: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def get_system_health() -> HealthResponse:
    """Get comprehensive system health status."""
    try:
        health_data = await health_checker.get_system_health()
        return HealthResponse(**health_data)
        
    except Exception as e:
        logger.error("Failed to get system health", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get system health")


@router.get("/health/{check_name}")
async def get_health_check(check_name: str) -> Dict[str, Any]:
    """Get specific health check result."""
    try:
        result = await health_checker.run_check(check_name)
        
        return {
            "name": result.name,
            "status": result.status.value,
            "message": result.message,
            "duration_ms": result.duration_ms,
            "timestamp": result.timestamp,
            "details": result.details or {}
        }
        
    except Exception as e:
        logger.error("Failed to run health check", error=str(e), check_name=check_name)
        raise HTTPException(status_code=500, detail="Failed to run health check")


@router.get("/metrics")
async def get_prometheus_metrics():
    """Get Prometheus metrics in text format."""
    try:
        metrics_data = metrics_manager.get_metrics_data()
        content_type = metrics_manager.get_content_type()
        
        return Response(
            content=metrics_data,
            media_type=content_type
        )
        
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get metrics")


@router.get("/stats")
async def get_system_stats() -> Dict[str, Any]:
    """Get system statistics and metrics."""
    try:
        # Get tenant usage stats
        from ....core.tenant import get_tenant_manager
        tenant_manager = await get_tenant_manager()
        tenant_stats = await tenant_manager.get_tenant_usage_stats()
        
        # Get queue stats
        from ....queue import get_queue_manager
        queue_manager = get_queue_manager()
        queue_stats = await queue_manager.get_queue_stats()
        
        # Get proxy stats
        from ....core.proxy import get_proxy_manager
        proxy_manager = get_proxy_manager()
        proxy_stats = await proxy_manager.get_stats()
        
        # Get health check summary
        health_data = await health_checker.get_system_health()
        
        # Get system resource info
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "timestamp": health_data["timestamp"],
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_total_gb": round(memory.total / 1024**3, 2),
                "memory_available_gb": round(memory.available / 1024**3, 2),
                "disk_percent": round((disk.used / disk.total) * 100, 1),
                "disk_total_gb": round(disk.total / 1024**3, 2),
                "disk_free_gb": round(disk.free / 1024**3, 2),
            },
            "health": {
                "overall_status": health_data["status"],
                "healthy_checks": health_data["summary"]["healthy"],
                "unhealthy_checks": health_data["summary"]["unhealthy"],
                "total_checks": health_data["summary"]["total_checks"],
            },
            "tenants": tenant_stats,
            "queue": queue_stats,
            "proxies": proxy_stats,
        }
        
    except Exception as e:
        logger.error("Failed to get system stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get system stats")


@router.post("/health/reset")
async def reset_health_checks() -> Dict[str, str]:
    """Reset and re-run all health checks."""
    try:
        await health_checker.run_all_checks()
        return {"message": "Health checks reset and re-run"}
        
    except Exception as e:
        logger.error("Failed to reset health checks", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reset health checks")


@router.get("/performance")
async def get_performance_metrics() -> Dict[str, Any]:
    """Get performance and timing metrics."""
    try:
        # This would normally come from metrics collection
        # For now, return basic system performance info
        import psutil
        import time
        
        # Get load averages (Unix-like systems only)
        try:
            load_avg = psutil.getloadavg()
        except AttributeError:
            load_avg = None
            
        # Get network I/O
        network_io = psutil.net_io_counters()
        
        # Get disk I/O
        disk_io = psutil.disk_io_counters()
        
        return {
            "timestamp": time.time(),
            "cpu": {
                "percent": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count(),
                "load_avg_1min": load_avg[0] if load_avg else None,
                "load_avg_5min": load_avg[1] if load_avg else None,
                "load_avg_15min": load_avg[2] if load_avg else None,
            },
            "memory": {
                "percent": psutil.virtual_memory().percent,
                "total_bytes": psutil.virtual_memory().total,
                "available_bytes": psutil.virtual_memory().available,
                "used_bytes": psutil.virtual_memory().used,
            },
            "network": {
                "bytes_sent": network_io.bytes_sent,
                "bytes_recv": network_io.bytes_recv,
                "packets_sent": network_io.packets_sent,
                "packets_recv": network_io.packets_recv,
            },
            "disk": {
                "read_bytes": disk_io.read_bytes,
                "write_bytes": disk_io.write_bytes,
                "read_count": disk_io.read_count,
                "write_count": disk_io.write_count,
            } if disk_io else None,
        }
        
    except Exception as e:
        logger.error("Failed to get performance metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")