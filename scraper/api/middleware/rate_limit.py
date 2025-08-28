"""
Rate Limiting Middleware

Implements rate limiting for API endpoints.
"""

import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from scraper.core.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = 60  # 1 minute window
        
        # In-memory storage: {api_key: [(timestamp, count), ...]}
        self._requests: Dict[str, list] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Apply rate limiting to requests."""
        
        # Skip rate limiting for health checks
        if request.url.path in ["/api/v1/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Get API key for rate limiting
        api_key = getattr(request.state, 'api_key', None)
        if not api_key:
            # Use IP address as fallback
            api_key = self._get_client_ip(request)
        
        # Check rate limit
        if await self._is_rate_limited(api_key):
            logger.warning("Rate limit exceeded", api_key=api_key[:8] + "...")
            return Response(
                content='{"error": "Rate limit exceeded", "retry_after": 60}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={"Retry-After": "60"}
            )
        
        # Record the request
        await self._record_request(api_key)
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
            
        return request.client.host if request.client else "unknown"
    
    async def _is_rate_limited(self, key: str) -> bool:
        """Check if the key has exceeded rate limits."""
        current_time = time.time()
        
        # Clean old requests outside the window
        self._requests[key] = [
            req for req in self._requests[key]
            if current_time - req[0] < self.window_size
        ]
        
        # Count requests in the current window
        request_count = sum(req[1] for req in self._requests[key])
        
        return request_count >= self.requests_per_minute
    
    async def _record_request(self, key: str) -> None:
        """Record a request for rate limiting."""
        current_time = time.time()
        
        # Add the current request
        self._requests[key].append((current_time, 1))
        
        # Cleanup old entries to prevent memory growth
        if len(self._requests[key]) > 100:
            self._requests[key] = self._requests[key][-50:]  # Keep last 50 entries