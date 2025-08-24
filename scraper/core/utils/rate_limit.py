"""Rate limiting utilities for controlling request frequency."""

import asyncio
import time
from typing import Dict, Optional

from scraper.core.config import get_config
from scraper.core.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter for async operations."""
    
    def __init__(self, rate: float, burst: Optional[int] = None):
        """
        Initialize rate limiter.
        
        Args:
            rate: Requests per second
            burst: Maximum burst size (defaults to rate * 2)
        """
        self.rate = rate
        self.burst = burst or max(1, int(rate * 2))
        self.tokens = self.burst
        self.last_update = time.time()
        self._lock = asyncio.Lock()
        
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, blocking if necessary."""
        async with self._lock:
            await self._wait_for_tokens(tokens)
            self.tokens -= tokens
            
    async def _wait_for_tokens(self, tokens: int) -> None:
        """Wait for sufficient tokens to become available."""
        while True:
            now = time.time()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            new_tokens = elapsed * self.rate
            self.tokens = min(self.burst, self.tokens + new_tokens)
            self.last_update = now
            
            if self.tokens >= tokens:
                break
                
            # Calculate wait time for next token
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait_time)
    
    def can_proceed(self, tokens: int = 1) -> bool:
        """Check if we can proceed without blocking."""
        now = time.time()
        elapsed = now - self.last_update
        available_tokens = min(self.burst, self.tokens + elapsed * self.rate)
        return available_tokens >= tokens


class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts based on server responses."""
    
    def __init__(self, initial_rate: float, min_rate: float = 0.1, max_rate: float = 10.0):
        """
        Initialize adaptive rate limiter.
        
        Args:
            initial_rate: Initial rate in requests per second
            min_rate: Minimum allowed rate
            max_rate: Maximum allowed rate
        """
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.limiter = RateLimiter(initial_rate)
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self._lock = asyncio.Lock()
        
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens using current rate."""
        await self.limiter.acquire(tokens)
        
    async def record_success(self) -> None:
        """Record a successful request."""
        async with self._lock:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            
            # Gradually increase rate after sustained success
            if self.consecutive_successes >= 10:
                old_rate = self.current_rate
                self.current_rate = min(self.max_rate, self.current_rate * 1.1)
                if self.current_rate != old_rate:
                    self.limiter = RateLimiter(self.current_rate)
                    logger.debug(f"Increased rate limit to {self.current_rate:.2f} req/s")
                self.consecutive_successes = 0
                
    async def record_failure(self, status_code: Optional[int] = None) -> None:
        """Record a failed request."""
        async with self._lock:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            
            # Aggressively reduce rate on 429 (Too Many Requests)
            if status_code == 429:
                old_rate = self.current_rate
                self.current_rate = max(self.min_rate, self.current_rate * 0.5)
                self.limiter = RateLimiter(self.current_rate)
                logger.warning(f"Rate limited (429), reduced to {self.current_rate:.2f} req/s")
                
            # Reduce rate after sustained failures
            elif self.consecutive_failures >= 5:
                old_rate = self.current_rate
                self.current_rate = max(self.min_rate, self.current_rate * 0.8)
                if self.current_rate != old_rate:
                    self.limiter = RateLimiter(self.current_rate)
                    logger.warning(f"Multiple failures, reduced rate to {self.current_rate:.2f} req/s")
                self.consecutive_failures = 0


class DomainRateLimiter:
    """Per-domain rate limiting manager."""
    
    def __init__(self):
        """Initialize domain rate limiter."""
        config = get_config()
        self.global_rate = config.concurrency.global_rate_limit
        self.domain_rate = config.concurrency.domain_rate_limit
        
        self.global_limiter = AdaptiveRateLimiter(self.global_rate)
        self.domain_limiters: Dict[str, AdaptiveRateLimiter] = {}
        self._lock = asyncio.Lock()
        
    async def acquire(self, domain: str) -> None:
        """Acquire permission to make request to domain."""
        # Always check global rate limit first
        await self.global_limiter.acquire()
        
        # Get or create domain-specific limiter
        domain_limiter = await self._get_domain_limiter(domain)
        await domain_limiter.acquire()
        
    async def _get_domain_limiter(self, domain: str) -> AdaptiveRateLimiter:
        """Get or create rate limiter for domain."""
        if domain not in self.domain_limiters:
            async with self._lock:
                if domain not in self.domain_limiters:
                    self.domain_limiters[domain] = AdaptiveRateLimiter(self.domain_rate)
        return self.domain_limiters[domain]
        
    async def record_success(self, domain: str) -> None:
        """Record successful request for domain."""
        await self.global_limiter.record_success()
        domain_limiter = await self._get_domain_limiter(domain)
        await domain_limiter.record_success()
        
    async def record_failure(self, domain: str, status_code: Optional[int] = None) -> None:
        """Record failed request for domain."""
        await self.global_limiter.record_failure(status_code)
        domain_limiter = await self._get_domain_limiter(domain)
        await domain_limiter.record_failure(status_code)
        
    def get_current_rates(self) -> Dict[str, float]:
        """Get current rates for all domains."""
        rates = {"global": self.global_limiter.current_rate}
        rates.update({
            domain: limiter.current_rate 
            for domain, limiter in self.domain_limiters.items()
        })
        return rates


class RateLimitContext:
    """Context manager for rate-limited operations."""
    
    def __init__(self, rate_limiter: DomainRateLimiter, domain: str):
        self.rate_limiter = rate_limiter
        self.domain = domain
        self.start_time = None
        
    async def __aenter__(self):
        """Acquire rate limit permission."""
        await self.rate_limiter.acquire(self.domain)
        self.start_time = time.time()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Record success/failure based on exception."""
        if exc_type is None:
            await self.rate_limiter.record_success(self.domain)
        else:
            # Extract status code from exception if available
            status_code = None
            if hasattr(exc_val, 'status_code'):
                status_code = exc_val.status_code
            elif hasattr(exc_val, 'status'):
                status_code = exc_val.status
                
            await self.rate_limiter.record_failure(self.domain, status_code)


# Global domain rate limiter instance
_domain_rate_limiter: Optional[DomainRateLimiter] = None


def get_domain_rate_limiter() -> DomainRateLimiter:
    """Get global domain rate limiter instance."""
    global _domain_rate_limiter
    if _domain_rate_limiter is None:
        _domain_rate_limiter = DomainRateLimiter()
    return _domain_rate_limiter


async def rate_limited(domain: str):
    """Context manager for rate-limited requests."""
    rate_limiter = get_domain_rate_limiter()
    return RateLimitContext(rate_limiter, domain)