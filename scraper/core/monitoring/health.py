"""Enhanced health checking system."""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass, field
import aiohttp

from ..logger import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health check status levels."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    
    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: float = field(default_factory=time.time)
    details: Optional[Dict[str, Any]] = None
    

@dataclass 
class HealthCheckConfig:
    """Configuration for a health check."""
    
    name: str
    check_func: Callable[[], Awaitable[HealthCheckResult]]
    timeout_seconds: float = 5.0
    required: bool = True
    tags: List[str] = field(default_factory=list)


class HealthChecker:
    """Manages system health checks."""
    
    def __init__(self) -> None:
        self._checks: Dict[str, HealthCheckConfig] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._check_interval = 30.0  # seconds
        self._background_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def initialize(self) -> None:
        """Initialize health checker."""
        try:
            # Register core health checks
            await self._register_core_checks()
            
            # Start background health checking
            await self.start_background_checks()
            
            logger.info("Health checker initialized")
            
        except Exception as e:
            logger.error("Failed to initialize health checker", error=str(e))
            raise
            
    async def _register_core_checks(self) -> None:
        """Register core system health checks."""
        
        # Database health check
        self.register_check(HealthCheckConfig(
            name="database",
            check_func=self._check_database_health,
            timeout_seconds=5.0,
            required=True,
            tags=["database", "persistence"]
        ))
        
        # Redis/Queue health check  
        self.register_check(HealthCheckConfig(
            name="queue",
            check_func=self._check_queue_health,
            timeout_seconds=3.0,
            required=True,
            tags=["queue", "redis"]
        ))
        
        # Memory usage check
        self.register_check(HealthCheckConfig(
            name="memory",
            check_func=self._check_memory_usage,
            timeout_seconds=1.0,
            required=False,
            tags=["system", "resources"]
        ))
        
        # Disk space check
        self.register_check(HealthCheckConfig(
            name="disk",
            check_func=self._check_disk_space,
            timeout_seconds=1.0,
            required=False,
            tags=["system", "storage"]
        ))
        
        # External connectivity check
        self.register_check(HealthCheckConfig(
            name="external_connectivity",
            check_func=self._check_external_connectivity,
            timeout_seconds=10.0,
            required=False,
            tags=["network", "external"]
        ))
        
    def register_check(self, config: HealthCheckConfig) -> None:
        """Register a health check."""
        self._checks[config.name] = config
        logger.debug(f"Registered health check: {config.name}")
        
    def unregister_check(self, name: str) -> None:
        """Unregister a health check."""
        if name in self._checks:
            del self._checks[name]
            if name in self._last_results:
                del self._last_results[name]
            logger.debug(f"Unregistered health check: {name}")
            
    async def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="Check not found",
                duration_ms=0.0
            )
            
        config = self._checks[name]
        start_time = time.time()
        
        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                config.check_func(), 
                timeout=config.timeout_seconds
            )
            
            # Cache result
            self._last_results[name] = result
            return result
            
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {config.timeout_seconds}s",
                duration_ms=duration_ms
            )
            self._last_results[name] = result
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                duration_ms=duration_ms,
                details={"error_type": type(e).__name__}
            )
            self._last_results[name] = result
            return result
            
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        results = {}
        
        # Run checks in parallel
        tasks = {
            name: asyncio.create_task(self.run_check(name))
            for name in self._checks.keys()
        }
        
        # Wait for all checks to complete
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                results[name] = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Task failed: {str(e)}",
                    duration_ms=0.0
                )
                
        return results
        
    async def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        results = await self.run_all_checks()
        
        # Determine overall status
        overall_status = HealthStatus.HEALTHY
        required_unhealthy = []
        optional_unhealthy = []
        
        for name, result in results.items():
            config = self._checks[name]
            
            if result.status == HealthStatus.UNHEALTHY:
                if config.required:
                    required_unhealthy.append(name)
                    overall_status = HealthStatus.UNHEALTHY
                else:
                    optional_unhealthy.append(name)
                    if overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.DEGRADED
                        
        # Build response
        return {
            "status": overall_status.value,
            "timestamp": time.time(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "duration_ms": result.duration_ms,
                    "timestamp": result.timestamp,
                    "required": self._checks[name].required,
                    "tags": self._checks[name].tags,
                    "details": result.details or {}
                }
                for name, result in results.items()
            },
            "summary": {
                "total_checks": len(results),
                "healthy": len([r for r in results.values() if r.status == HealthStatus.HEALTHY]),
                "degraded": len([r for r in results.values() if r.status == HealthStatus.DEGRADED]),
                "unhealthy": len([r for r in results.values() if r.status == HealthStatus.UNHEALTHY]),
                "required_unhealthy": required_unhealthy,
                "optional_unhealthy": optional_unhealthy
            }
        }
        
    async def get_cached_results(self) -> Dict[str, HealthCheckResult]:
        """Get cached health check results."""
        return self._last_results.copy()
        
    async def start_background_checks(self) -> None:
        """Start background health checking."""
        if self._running:
            return
            
        self._running = True
        self._background_task = asyncio.create_task(self._background_check_loop())
        logger.info("Started background health checks")
        
    async def stop_background_checks(self) -> None:
        """Stop background health checking."""
        self._running = False
        
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Stopped background health checks")
        
    async def _background_check_loop(self) -> None:
        """Background loop for periodic health checks."""
        while self._running:
            try:
                # Run all checks
                await self.run_all_checks()
                
                # Wait for next interval
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Background health check failed", error=str(e))
                await asyncio.sleep(5)  # Short delay on error
                
    async def _check_database_health(self) -> HealthCheckResult:
        """Check database connectivity."""
        start_time = time.time()
        
        try:
            from ...database import get_database_manager
            
            db = get_database_manager()
            
            # Simple query to test connectivity
            if hasattr(db, 'execute'):
                await db.execute("SELECT 1")
            else:
                # Fallback for different database implementations
                pass
                
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connection healthy",
                duration_ms=duration_ms,
                details={
                    "type": getattr(db, 'db_type', 'unknown'),
                    "connected": True
                }
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database check failed: {str(e)}",
                duration_ms=duration_ms,
                details={
                    "error": str(e),
                    "connected": False
                }
            )
            
    async def _check_queue_health(self) -> HealthCheckResult:
        """Check queue/Redis connectivity."""
        start_time = time.time()
        
        try:
            from ...queue import get_queue_manager
            
            queue_manager = get_queue_manager()
            
            # Test queue connectivity
            stats = await queue_manager.get_queue_stats()
            
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name="queue",
                status=HealthStatus.HEALTHY,
                message="Queue system healthy",
                duration_ms=duration_ms,
                details={
                    "backend": getattr(queue_manager, 'backend_type', 'unknown'),
                    "stats": stats
                }
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name="queue",
                status=HealthStatus.UNHEALTHY,
                message=f"Queue check failed: {str(e)}",
                duration_ms=duration_ms,
                details={
                    "error": str(e)
                }
            )
            
    async def _check_memory_usage(self) -> HealthCheckResult:
        """Check system memory usage."""
        import psutil
        
        start_time = time.time()
        
        try:
            memory = psutil.virtual_memory()
            duration_ms = (time.time() - start_time) * 1000
            
            # Determine status based on usage
            if memory.percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"High memory usage: {memory.percent:.1f}%"
            elif memory.percent > 80:
                status = HealthStatus.DEGRADED
                message = f"Elevated memory usage: {memory.percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory.percent:.1f}%"
                
            return HealthCheckResult(
                name="memory",
                status=status,
                message=message,
                duration_ms=duration_ms,
                details={
                    "percent_used": memory.percent,
                    "total_gb": round(memory.total / 1024**3, 2),
                    "available_gb": round(memory.available / 1024**3, 2)
                }
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=f"Memory check failed: {str(e)}",
                duration_ms=duration_ms
            )
            
    async def _check_disk_space(self) -> HealthCheckResult:
        """Check disk space usage."""
        import psutil
        
        start_time = time.time()
        
        try:
            disk = psutil.disk_usage('/')
            duration_ms = (time.time() - start_time) * 1000
            
            percent_used = (disk.used / disk.total) * 100
            
            # Determine status based on usage
            if percent_used > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk usage: {percent_used:.1f}%"
            elif percent_used > 85:
                status = HealthStatus.DEGRADED
                message = f"High disk usage: {percent_used:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage normal: {percent_used:.1f}%"
                
            return HealthCheckResult(
                name="disk",
                status=status,
                message=message,
                duration_ms=duration_ms,
                details={
                    "percent_used": round(percent_used, 1),
                    "total_gb": round(disk.total / 1024**3, 2),
                    "free_gb": round(disk.free / 1024**3, 2)
                }
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.UNKNOWN,
                message=f"Disk check failed: {str(e)}",
                duration_ms=duration_ms
            )
            
    async def _check_external_connectivity(self) -> HealthCheckResult:
        """Check external network connectivity."""
        start_time = time.time()
        
        try:
            # Test connectivity to a reliable external service
            timeout = aiohttp.ClientTimeout(total=5)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get('https://httpbin.org/status/200') as response:
                    if response.status == 200:
                        duration_ms = (time.time() - start_time) * 1000
                        
                        return HealthCheckResult(
                            name="external_connectivity",
                            status=HealthStatus.HEALTHY,
                            message="External connectivity working",
                            duration_ms=duration_ms,
                            details={
                                "test_url": "https://httpbin.org/status/200",
                                "status_code": response.status
                            }
                        )
                    else:
                        raise Exception(f"Unexpected status code: {response.status}")
                        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name="external_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"External connectivity failed: {str(e)}",
                duration_ms=duration_ms,
                details={
                    "error": str(e)
                }
            )
            
    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.stop_background_checks()
        self._checks.clear()
        self._last_results.clear()
        logger.info("Health checker cleaned up")


# Global health checker instance
health_checker = HealthChecker()