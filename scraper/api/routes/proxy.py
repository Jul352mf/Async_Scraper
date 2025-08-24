"""
Proxy management API endpoints.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from scraper.api.middleware.auth import get_current_api_key
from scraper.core.logger import get_logger
from scraper.core.proxy import ProxyManager, Proxy, ProxyConfig, ProxyRotationStrategy
from scraper.core.proxy.models import ProxyStatus

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/proxy", tags=["Proxy Management"])

# Global proxy manager (to be initialized by the main app)
_proxy_manager: Optional[ProxyManager] = None


def get_proxy_manager() -> ProxyManager:
    """Get the global proxy manager instance."""
    if _proxy_manager is None:
        raise HTTPException(status_code=503, detail="Proxy manager not initialized")
    return _proxy_manager


def set_proxy_manager(proxy_manager: ProxyManager) -> None:
    """Set the global proxy manager instance."""
    global _proxy_manager
    _proxy_manager = proxy_manager


# Pydantic models for API
class ProxyCreateRequest(BaseModel):
    """Request model for creating a proxy."""
    url: str = Field(..., description="Proxy URL")
    description: Optional[str] = Field(None, description="Proxy description")
    country: Optional[str] = Field(None, description="Proxy country")
    region: Optional[str] = Field(None, description="Proxy region")
    tags: List[str] = Field(default_factory=list, description="Proxy tags")


class ProxyUpdateRequest(BaseModel):
    """Request model for updating a proxy."""
    description: Optional[str] = Field(None, description="Proxy description")
    country: Optional[str] = Field(None, description="Proxy country")
    region: Optional[str] = Field(None, description="Proxy region")
    tags: Optional[List[str]] = Field(None, description="Proxy tags")
    enabled: Optional[bool] = Field(None, description="Enable/disable proxy")


class ProxyResponse(BaseModel):
    """Response model for proxy data."""
    id: str
    url: str
    proxy_type: str
    host: str
    port: int
    country: Optional[str]
    region: Optional[str]
    description: Optional[str]
    tags: List[str]
    enabled: bool
    created_at: datetime
    last_used: Optional[datetime]
    use_count: int
    
    # Health information
    status: str
    last_checked: Optional[datetime]
    response_time: Optional[float]
    success_count: int
    failure_count: int
    consecutive_failures: int
    success_rate: float


class ProxyStatsResponse(BaseModel):
    """Response model for proxy statistics."""
    total_proxies: int
    enabled_proxies: int
    healthy_proxies: int
    average_response_time: float
    status_distribution: Dict[str, int]
    rotation_strategy: str


class ProxyConfigResponse(BaseModel):
    """Response model for proxy configuration."""
    enabled: bool
    rotation_strategy: str
    health_check_interval: int
    health_check_timeout: int
    health_check_url: str
    max_consecutive_failures: int
    blacklist_duration: int
    fallback_to_direct: bool
    retry_failed_proxies: bool
    geographic_preference: Optional[str]


class ProxyConfigUpdateRequest(BaseModel):
    """Request model for updating proxy configuration."""
    rotation_strategy: Optional[str] = Field(None, description="Proxy rotation strategy")
    health_check_interval: Optional[int] = Field(None, description="Health check interval in seconds")
    health_check_timeout: Optional[int] = Field(None, description="Health check timeout in seconds")
    health_check_url: Optional[str] = Field(None, description="Health check URL")
    max_consecutive_failures: Optional[int] = Field(None, description="Max consecutive failures")
    blacklist_duration: Optional[int] = Field(None, description="Blacklist duration in seconds")
    fallback_to_direct: Optional[bool] = Field(None, description="Fallback to direct connection")
    retry_failed_proxies: Optional[bool] = Field(None, description="Retry failed proxies")
    geographic_preference: Optional[str] = Field(None, description="Geographic preference")


# API endpoints
@router.get("/proxies", response_model=List[ProxyResponse])
async def list_proxies(
    enabled_only: bool = Query(False, description="Filter by enabled proxies only"),
    healthy_only: bool = Query(False, description="Filter by healthy proxies only"),
    api_key: str = Depends(get_current_api_key)
) -> List[ProxyResponse]:
    """List all proxies with optional filtering."""
    try:
        proxy_manager = get_proxy_manager()
        proxies = proxy_manager.list_proxies(enabled_only=enabled_only, healthy_only=healthy_only)
        
        return [
            ProxyResponse(
                id=proxy.id,
                url=proxy.url,
                proxy_type=proxy.effective_proxy_type.value,
                host=proxy.effective_host,
                port=proxy.effective_port,
                country=proxy.country,
                region=proxy.region,
                description=proxy.description,
                tags=proxy.tags,
                enabled=proxy.enabled,
                created_at=proxy.created_at,
                last_used=proxy.last_used,
                use_count=proxy.use_count,
                status=proxy.health.status.value,
                last_checked=proxy.health.last_checked,
                response_time=proxy.health.response_time,
                success_count=proxy.health.success_count,
                failure_count=proxy.health.failure_count,
                consecutive_failures=proxy.health.consecutive_failures,
                success_rate=proxy.health.success_rate
            )
            for proxy in proxies
        ]
    except Exception as e:
        logger.error("Failed to list proxies", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list proxies")


@router.post("/proxies", response_model=ProxyResponse)
async def create_proxy(
    request: ProxyCreateRequest,
    api_key: str = Depends(get_current_api_key)
) -> ProxyResponse:
    """Create a new proxy."""
    try:
        proxy_manager = get_proxy_manager()
        
        # Create proxy from URL
        proxy = Proxy(
            url=request.url,
            description=request.description,
            country=request.country,
            region=request.region,
            tags=request.tags
        )
        
        proxy_manager.add_proxy(proxy)
        logger.info("Created new proxy", proxy_id=proxy.id, url=request.url)
        
        return ProxyResponse(
            id=proxy.id,
            url=proxy.url,
            proxy_type=proxy.effective_proxy_type.value,
            host=proxy.effective_host,
            port=proxy.effective_port,
            country=proxy.country,
            region=proxy.region,
            description=proxy.description,
            tags=proxy.tags,
            enabled=proxy.enabled,
            created_at=proxy.created_at,
            last_used=proxy.last_used,
            use_count=proxy.use_count,
            status=proxy.health.status.value,
            last_checked=proxy.health.last_checked,
            response_time=proxy.health.response_time,
            success_count=proxy.health.success_count,
            failure_count=proxy.health.failure_count,
            consecutive_failures=proxy.health.consecutive_failures,
            success_rate=proxy.health.success_rate
        )
        
    except ValueError as e:
        logger.warning("Invalid proxy URL", url=request.url, error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid proxy URL: {str(e)}")
    except Exception as e:
        logger.error("Failed to create proxy", url=request.url, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create proxy")


@router.get("/proxies/{proxy_id}", response_model=ProxyResponse)
async def get_proxy(
    proxy_id: str,
    api_key: str = Depends(get_current_api_key)
) -> ProxyResponse:
    """Get a specific proxy by ID."""
    try:
        proxy_manager = get_proxy_manager()
        proxy = proxy_manager.get_proxy(proxy_id)
        
        if not proxy:
            raise HTTPException(status_code=404, detail="Proxy not found")
        
        return ProxyResponse(
            id=proxy.id,
            url=proxy.url,
            proxy_type=proxy.effective_proxy_type.value,
            host=proxy.effective_host,
            port=proxy.effective_port,
            country=proxy.country,
            region=proxy.region,
            description=proxy.description,
            tags=proxy.tags,
            enabled=proxy.enabled,
            created_at=proxy.created_at,
            last_used=proxy.last_used,
            use_count=proxy.use_count,
            status=proxy.health.status.value,
            last_checked=proxy.health.last_checked,
            response_time=proxy.health.response_time,
            success_count=proxy.health.success_count,
            failure_count=proxy.health.failure_count,
            consecutive_failures=proxy.health.consecutive_failures,
            success_rate=proxy.health.success_rate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get proxy", proxy_id=proxy_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get proxy")


@router.put("/proxies/{proxy_id}", response_model=ProxyResponse)
async def update_proxy(
    proxy_id: str,
    request: ProxyUpdateRequest,
    api_key: str = Depends(get_current_api_key)
) -> ProxyResponse:
    """Update a proxy."""
    try:
        proxy_manager = get_proxy_manager()
        proxy = proxy_manager.get_proxy(proxy_id)
        
        if not proxy:
            raise HTTPException(status_code=404, detail="Proxy not found")
        
        # Build updates dictionary
        updates = {}
        if request.description is not None:
            updates["description"] = request.description
        if request.country is not None:
            updates["country"] = request.country
        if request.region is not None:
            updates["region"] = request.region
        if request.tags is not None:
            updates["tags"] = request.tags
        if request.enabled is not None:
            updates["enabled"] = request.enabled
        
        success = proxy_manager.update_proxy(proxy_id, updates)
        if not success:
            raise HTTPException(status_code=404, detail="Proxy not found")
        
        # Get updated proxy
        proxy = proxy_manager.get_proxy(proxy_id)
        
        return ProxyResponse(
            id=proxy.id,
            url=proxy.url,
            proxy_type=proxy.effective_proxy_type.value,
            host=proxy.effective_host,
            port=proxy.effective_port,
            country=proxy.country,
            region=proxy.region,
            description=proxy.description,
            tags=proxy.tags,
            enabled=proxy.enabled,
            created_at=proxy.created_at,
            last_used=proxy.last_used,
            use_count=proxy.use_count,
            status=proxy.health.status.value,
            last_checked=proxy.health.last_checked,
            response_time=proxy.health.response_time,
            success_count=proxy.health.success_count,
            failure_count=proxy.health.failure_count,
            consecutive_failures=proxy.health.consecutive_failures,
            success_rate=proxy.health.success_rate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update proxy", proxy_id=proxy_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update proxy")


@router.delete("/proxies/{proxy_id}")
async def delete_proxy(
    proxy_id: str,
    api_key: str = Depends(get_current_api_key)
) -> Dict[str, str]:
    """Delete a proxy."""
    try:
        proxy_manager = get_proxy_manager()
        success = proxy_manager.remove_proxy(proxy_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Proxy not found")
        
        logger.info("Deleted proxy", proxy_id=proxy_id)
        return {"message": "Proxy deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete proxy", proxy_id=proxy_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete proxy")


@router.post("/proxies/{proxy_id}/health-check")
async def check_proxy_health(
    proxy_id: str,
    api_key: str = Depends(get_current_api_key)
) -> Dict[str, Any]:
    """Perform health check on a specific proxy."""
    try:
        proxy_manager = get_proxy_manager()
        success = await proxy_manager.check_proxy_health(proxy_id)
        
        proxy = proxy_manager.get_proxy(proxy_id)
        if not proxy:
            raise HTTPException(status_code=404, detail="Proxy not found")
        
        return {
            "proxy_id": proxy_id,
            "health_check_passed": success,
            "status": proxy.health.status.value,
            "response_time": proxy.health.response_time,
            "last_checked": proxy.health.last_checked,
            "consecutive_failures": proxy.health.consecutive_failures
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to check proxy health", proxy_id=proxy_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to check proxy health")


@router.post("/proxies/health-check-all")
async def check_all_proxies_health(
    api_key: str = Depends(get_current_api_key)
) -> Dict[str, Any]:
    """Perform health check on all proxies."""
    try:
        proxy_manager = get_proxy_manager()
        results = await proxy_manager.check_all_proxies_health()
        
        return {
            "total_proxies_checked": len(results),
            "healthy_proxies": sum(1 for success in results.values() if success),
            "unhealthy_proxies": sum(1 for success in results.values() if not success),
            "results": results
        }
        
    except Exception as e:
        logger.error("Failed to check all proxies health", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to check all proxies health")


@router.get("/stats", response_model=ProxyStatsResponse)
async def get_proxy_stats(
    api_key: str = Depends(get_current_api_key)
) -> ProxyStatsResponse:
    """Get proxy system statistics."""
    try:
        proxy_manager = get_proxy_manager()
        stats = proxy_manager.get_proxy_stats()
        
        return ProxyStatsResponse(**stats)
        
    except Exception as e:
        logger.error("Failed to get proxy stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get proxy stats")


@router.get("/config", response_model=ProxyConfigResponse)
async def get_proxy_config(
    api_key: str = Depends(get_current_api_key)
) -> ProxyConfigResponse:
    """Get proxy configuration."""
    try:
        proxy_manager = get_proxy_manager()
        config = proxy_manager.config
        
        return ProxyConfigResponse(
            enabled=config.enabled,
            rotation_strategy=config.rotation_strategy.value,
            health_check_interval=config.health_check_interval,
            health_check_timeout=config.health_check_timeout,
            health_check_url=config.health_check_url,
            max_consecutive_failures=config.max_consecutive_failures,
            blacklist_duration=config.blacklist_duration,
            fallback_to_direct=config.fallback_to_direct,
            retry_failed_proxies=config.retry_failed_proxies,
            geographic_preference=config.geographic_preference
        )
        
    except Exception as e:
        logger.error("Failed to get proxy config", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get proxy config")


@router.put("/config", response_model=ProxyConfigResponse)
async def update_proxy_config(
    request: ProxyConfigUpdateRequest,
    api_key: str = Depends(get_current_api_key)
) -> ProxyConfigResponse:
    """Update proxy configuration."""
    try:
        proxy_manager = get_proxy_manager()
        
        # Update configuration
        if request.rotation_strategy:
            strategy = ProxyRotationStrategy(request.rotation_strategy)
            proxy_manager.set_rotation_strategy(strategy)
        
        if request.geographic_preference is not None:
            proxy_manager.set_geographic_preference(request.geographic_preference)
        
        # Update other config fields
        config = proxy_manager.config
        if request.health_check_interval is not None:
            config.health_check_interval = request.health_check_interval
        if request.health_check_timeout is not None:
            config.health_check_timeout = request.health_check_timeout
        if request.health_check_url is not None:
            config.health_check_url = request.health_check_url
        if request.max_consecutive_failures is not None:
            config.max_consecutive_failures = request.max_consecutive_failures
        if request.blacklist_duration is not None:
            config.blacklist_duration = request.blacklist_duration
        if request.fallback_to_direct is not None:
            config.fallback_to_direct = request.fallback_to_direct
        if request.retry_failed_proxies is not None:
            config.retry_failed_proxies = request.retry_failed_proxies
        
        logger.info("Updated proxy configuration")
        
        return ProxyConfigResponse(
            enabled=config.enabled,
            rotation_strategy=config.rotation_strategy.value,
            health_check_interval=config.health_check_interval,
            health_check_timeout=config.health_check_timeout,
            health_check_url=config.health_check_url,
            max_consecutive_failures=config.max_consecutive_failures,
            blacklist_duration=config.blacklist_duration,
            fallback_to_direct=config.fallback_to_direct,
            retry_failed_proxies=config.retry_failed_proxies,
            geographic_preference=config.geographic_preference
        )
        
    except ValueError as e:
        logger.warning("Invalid proxy configuration", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to update proxy config", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update proxy config")