"""FastAPI middleware for tenant handling."""

import time
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .manager import get_tenant_manager
from .models import TenantModel
from ..logger import get_logger
from ..monitoring import metrics_manager

logger = get_logger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to handle tenant resolution and rate limiting."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with tenant context."""
        start_time = time.time()
        tenant = None
        tenant_id = "unknown"
        
        try:
            # Extract API key from headers
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                # Try query parameter
                api_key = request.query_params.get("api_key")
                
            if api_key:
                # Resolve tenant from API key
                tenant_manager = await get_tenant_manager()
                tenant = await tenant_manager.get_tenant_by_api_key(api_key)
                
                if tenant:
                    tenant_id = tenant.tenant_id
                    
                    # Check if tenant can make request
                    if not tenant.can_make_request():
                        # Record rate limit exceeded
                        metrics_manager.increment_counter(
                            "rate_limit_exceeded_total",
                            {"api_key_id": api_key[:8], "tenant_id": tenant_id}
                        )
                        
                        raise HTTPException(
                            status_code=429,
                            detail="Rate limit exceeded"
                        )
                        
                    # Record request
                    tenant.record_request()
                    
                    # Store tenant in request state
                    request.state.tenant = tenant
                    request.state.api_key = api_key
                else:
                    # Invalid API key
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid API key"
                    )
            else:
                # No API key provided for protected endpoints
                if not self._is_public_endpoint(request.url.path):
                    raise HTTPException(
                        status_code=401,
                        detail="API key required"
                    )
                    
            # Process request
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            
            metrics_manager.increment_counter(
                "http_requests_total",
                {
                    "method": request.method,
                    "endpoint": request.url.path,
                    "status_code": str(response.status_code),
                    "tenant_id": tenant_id
                }
            )
            
            metrics_manager.observe_histogram(
                "http_request_duration_seconds",
                duration,
                {
                    "method": request.method,
                    "endpoint": request.url.path,
                    "tenant_id": tenant_id
                }
            )
            
            if tenant and api_key:
                metrics_manager.increment_counter(
                    "api_key_requests_total",
                    {"api_key_id": api_key[:8], "tenant_id": tenant_id}
                )
                
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error("Tenant middleware error", error=str(e))
            
            # Record error metrics
            duration = time.time() - start_time
            metrics_manager.increment_counter(
                "http_requests_total",
                {
                    "method": request.method,
                    "endpoint": request.url.path,
                    "status_code": "500",
                    "tenant_id": tenant_id
                }
            )
            
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )
            
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public (doesn't require API key)."""
        public_endpoints = [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/metrics",
        ]
        
        return any(path.startswith(endpoint) for endpoint in public_endpoints)


def get_current_tenant(request: Request) -> Optional[TenantModel]:
    """Get current tenant from request."""
    return getattr(request.state, "tenant", None)
    

def get_current_api_key(request: Request) -> Optional[str]:
    """Get current API key from request."""
    return getattr(request.state, "api_key", None)
    

def require_tenant(request: Request) -> TenantModel:
    """Require tenant to be present in request."""
    tenant = get_current_tenant(request)
    if not tenant:
        raise HTTPException(status_code=401, detail="Authentication required")
    return tenant
    

def require_feature(request: Request, feature: str) -> TenantModel:
    """Require tenant to have a specific feature."""
    tenant = require_tenant(request)
    
    if not tenant.has_feature(feature):
        raise HTTPException(
            status_code=403,
            detail=f"Feature '{feature}' not available for your plan"
        )
        
    return tenant