"""
Authentication Middleware

Handles API key authentication for requests.
"""

from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from scraper.core.logger import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication."""
    
    # Public endpoints that don't require authentication
    PUBLIC_PATHS = {
        "/health",
        "/docs",
        "/redoc", 
        "/openapi.json"
    }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process authentication for incoming requests."""
        
        # Skip authentication for public endpoints
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)
        
        # Skip for development
        if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return await call_next(request)
            
        # Get API key from headers
        api_key = self._extract_api_key(request)
        
        if not api_key:
            logger.warning("Request without API key", path=request.url.path)
            return Response(
                content='{"error": "API key required"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json"
            )
        
        # Validate API key (placeholder implementation)
        if not await self._validate_api_key(api_key):
            logger.warning("Invalid API key", api_key=api_key[:8] + "...")
            return Response(
                content='{"error": "Invalid API key"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json"
            )
        
        # Add authenticated user info to request state
        request.state.api_key = api_key
        request.state.authenticated = True
        
        return await call_next(request)
    
    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request headers."""
        
        # Check Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        
        # Check X-API-Key header
        return request.headers.get("X-API-Key")
    
    async def _validate_api_key(self, api_key: str) -> bool:
        """
        Validate the provided API key.
        
        TODO: Implement proper API key validation with database lookup
        """
        # Placeholder implementation - accept any non-empty key
        # In production, this should validate against a database
        return len(api_key) >= 8


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key (dependency function).
    
    Args:
        api_key: API key to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    return len(api_key) >= 8


def get_current_api_key(request: Request) -> str:
    """
    Get and validate the current API key from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: Validated API key
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    # Check Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        api_key = auth_header[7:]  # Remove "Bearer " prefix
    else:
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )
    
    if not validate_api_key(api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return api_key