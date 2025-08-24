"""Retry logic using tenacity for asynchronous operations."""

import asyncio
from typing import Any, Callable, Dict, Optional, Type, Union

from tenacity import (
    AsyncRetrying,
    RetryError,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
)

from scraper.core.config import get_config
from scraper.core.logger import get_logger

logger = get_logger(__name__)


class RetryableError(Exception):
    """Base class for retryable errors."""
    pass


class RateLimitError(RetryableError):
    """Error raised when rate limited (HTTP 429, etc.)."""
    pass


class NetworkError(RetryableError):
    """Network-related errors that should be retried."""
    pass


class ServerError(RetryableError):
    """Server errors (5xx) that should be retried."""
    pass


def get_retry_config() -> Dict[str, Any]:
    """Get retry configuration from global config."""
    config = get_config()
    return {
        "max_attempts": config.concurrency.retry_max_attempts,
        "backoff_factor": config.concurrency.retry_backoff_factor,
        "max_delay": config.concurrency.retry_max_delay,
    }


async def retry_async(
    func: Callable,
    *args,
    max_attempts: Optional[int] = None,
    backoff_factor: Optional[float] = None,
    max_delay: Optional[float] = None,
    retry_exceptions: tuple = (RetryableError,),
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Arguments to pass to func
        max_attempts: Maximum retry attempts
        backoff_factor: Exponential backoff factor
        max_delay: Maximum delay between retries
        retry_exceptions: Tuple of exception types to retry on
        **kwargs: Keyword arguments to pass to func
    
    Returns:
        Result of successful function call
    
    Raises:
        RetryError: If all retry attempts fail
    """
    # Get default config if not provided
    retry_config = get_retry_config()
    max_attempts = max_attempts or retry_config["max_attempts"]
    backoff_factor = backoff_factor or retry_config["backoff_factor"]
    max_delay = max_delay or retry_config["max_delay"]
    
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=backoff_factor,
            max=max_delay
        ),
        retry=retry_if_exception_type(retry_exceptions),
        before_sleep=before_sleep_log(logger, logger.info),
        reraise=True,
    ):
        with attempt:
            return await func(*args, **kwargs)


class RetryDecorator:
    """Decorator class for adding retry logic to async functions."""
    
    def __init__(
        self,
        max_attempts: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        max_delay: Optional[float] = None,
        retry_exceptions: tuple = (RetryableError,),
    ):
        retry_config = get_retry_config()
        self.max_attempts = max_attempts or retry_config["max_attempts"]
        self.backoff_factor = backoff_factor or retry_config["backoff_factor"]
        self.max_delay = max_delay or retry_config["max_delay"]
        self.retry_exceptions = retry_exceptions
    
    def __call__(self, func: Callable) -> Callable:
        """Apply retry logic to the decorated function."""
        async def wrapper(*args, **kwargs):
            return await retry_async(
                func,
                *args,
                max_attempts=self.max_attempts,
                backoff_factor=self.backoff_factor,
                max_delay=self.max_delay,
                retry_exceptions=self.retry_exceptions,
                **kwargs
            )
        return wrapper


def retry_on_failure(
    max_attempts: Optional[int] = None,
    backoff_factor: Optional[float] = None,
    max_delay: Optional[float] = None,
    retry_exceptions: tuple = (RetryableError,),
):
    """
    Decorator to add retry logic to async functions.
    
    Usage:
        @retry_on_failure(max_attempts=3, retry_exceptions=(NetworkError, RateLimitError))
        async def fetch_data():
            # Function implementation
            pass
    """
    return RetryDecorator(
        max_attempts=max_attempts,
        backoff_factor=backoff_factor,
        max_delay=max_delay,
        retry_exceptions=retry_exceptions,
    )


class AdaptiveRetry:
    """Adaptive retry strategy that adjusts based on response patterns."""
    
    def __init__(self):
        self.success_count = 0
        self.failure_count = 0
        self.consecutive_failures = 0
        
    def record_success(self) -> None:
        """Record a successful operation."""
        self.success_count += 1
        self.consecutive_failures = 0
        
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.consecutive_failures += 1
        
    def get_delay(self, attempt: int) -> float:
        """Get adaptive delay based on failure patterns."""
        base_delay = 2.0 ** attempt
        
        # Increase delay if we have many consecutive failures
        if self.consecutive_failures > 5:
            base_delay *= 2
        elif self.consecutive_failures > 10:
            base_delay *= 4
            
        # Success rate adjustment
        total_ops = self.success_count + self.failure_count
        if total_ops > 10:
            success_rate = self.success_count / total_ops
            if success_rate < 0.5:
                base_delay *= 1.5
                
        return min(base_delay, 120.0)  # Cap at 2 minutes
    
    async def retry_with_adaptive_delay(
        self,
        func: Callable,
        *args,
        max_attempts: int = 5,
        **kwargs
    ) -> Any:
        """Retry function with adaptive delay strategy."""
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
                
            except RetryableError as e:
                last_exception = e
                self.record_failure()
                
                if attempt < max_attempts - 1:
                    delay = self.get_delay(attempt)
                    logger.info(
                        "Retrying after failure",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        delay=delay,
                        error=str(e)
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Max retry attempts reached",
                        max_attempts=max_attempts,
                        consecutive_failures=self.consecutive_failures
                    )
                    
        raise RetryError(f"Failed after {max_attempts} attempts") from last_exception


# Global adaptive retry instance
_adaptive_retry = AdaptiveRetry()


async def adaptive_retry(
    func: Callable,
    *args,
    max_attempts: int = 5,
    **kwargs
) -> Any:
    """Use global adaptive retry strategy."""
    return await _adaptive_retry.retry_with_adaptive_delay(
        func, *args, max_attempts=max_attempts, **kwargs
    )