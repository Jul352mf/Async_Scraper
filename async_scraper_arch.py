"""
Async Scraper Architecture

High-performance, async-first web scraping framework providing:
- Asynchronous request handling with session management
- Rate limiting and throttling capabilities  
- Robust error handling and retry mechanisms
- Configurable request/response processing
- Extensible architecture for custom scrapers
"""

import asyncio
import aiohttp
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Union, AsyncGenerator
from urllib.parse import urljoin, urlparse


@dataclass
class ScrapingConfig:
    """Configuration for the async scraper."""
    
    # Rate limiting
    requests_per_second: float = 10.0
    burst_size: int = 20
    
    # Request settings
    timeout: int = 30
    max_redirects: int = 10
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_factor: float = 2.0
    
    # Session settings
    connector_limit: int = 100
    connector_limit_per_host: int = 30
    
    # Headers
    default_headers: Dict[str, str] = field(default_factory=lambda: {
        'User-Agent': 'AsyncScraper/1.0'
    })
    
    # Logging
    log_level: int = logging.INFO


@dataclass
class RequestData:
    """Data structure for scraping requests."""
    
    url: str
    method: str = 'GET'
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    data: Optional[Union[str, bytes, Dict]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass 
class ResponseData:
    """Data structure for scraping responses."""
    
    url: str
    status_code: int
    headers: Dict[str, str]
    content: bytes
    text: str
    request_metadata: Optional[Dict[str, Any]] = None
    response_time: float = 0.0
    
    @property
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return 200 <= self.status_code < 300


class RateLimiter:
    """Token bucket rate limiter for controlling request frequency."""
    
    def __init__(self, rate: float, burst_size: int):
        self.rate = rate  # requests per second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire a token, blocking if necessary."""
        async with self._lock:
            now = time.time()
            # Add tokens based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
            self.last_refill = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return
            
            # Wait until next token is available
            wait_time = (1 - self.tokens) / self.rate
            await asyncio.sleep(wait_time)
            self.tokens = 0


class AsyncScraperError(Exception):
    """Base exception for scraper errors."""
    pass


class RequestError(AsyncScraperError):
    """Exception raised for request-related errors."""
    
    def __init__(self, message: str, response: Optional[ResponseData] = None):
        super().__init__(message)
        self.response = response


class ResponseProcessor(ABC):
    """Abstract base class for response processors."""
    
    @abstractmethod
    async def process(self, response: ResponseData) -> Any:
        """Process a response and return extracted data."""
        pass


class DefaultResponseProcessor(ResponseProcessor):
    """Default response processor that returns the response as-is."""
    
    async def process(self, response: ResponseData) -> ResponseData:
        return response


class AsyncScraper:
    """
    High-performance async web scraper with rate limiting and session management.
    
    This class provides the core functionality for asynchronous web scraping:
    - Manages HTTP sessions with connection pooling
    - Implements rate limiting to respect server resources
    - Handles retries and error recovery
    - Supports custom response processing
    """
    
    def __init__(self, config: Optional[ScrapingConfig] = None):
        self.config = config or ScrapingConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimiter(
            self.config.requests_per_second,
            self.config.burst_size
        )
        self.logger = self._setup_logging()
        self._closed = False
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the scraper."""
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        logger.setLevel(self.config.log_level)
        return logger
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def start(self) -> None:
        """Initialize the scraper session."""
        if self.session is None:
            connector = aiohttp.TCPConnector(
                limit=self.config.connector_limit,
                limit_per_host=self.config.connector_limit_per_host
            )
            
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.config.default_headers
            )
            self.logger.info("AsyncScraper session initialized")
    
    async def close(self) -> None:
        """Close the scraper session and cleanup resources."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("AsyncScraper session closed")
        self._closed = True
    
    async def scrape(
        self, 
        request: RequestData, 
        processor: Optional[ResponseProcessor] = None
    ) -> Any:
        """
        Scrape a single URL.
        
        Args:
            request: Request data including URL and options
            processor: Optional response processor
            
        Returns:
            Processed response data
        """
        if self.session is None:
            await self.start()
        
        processor = processor or DefaultResponseProcessor()
        
        for attempt in range(self.config.max_retries + 1):
            try:
                await self.rate_limiter.acquire()
                
                start_time = time.time()
                response_data = await self._make_request(request)
                response_data.response_time = time.time() - start_time
                
                if response_data.is_success:
                    return await processor.process(response_data)
                else:
                    self.logger.warning(
                        f"Non-success status {response_data.status_code} for {request.url}"
                    )
                    
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout for {request.url} (attempt {attempt + 1})")
                if attempt == self.config.max_retries:
                    raise RequestError(f"Timeout after {self.config.max_retries + 1} attempts")
                    
            except Exception as e:
                self.logger.warning(f"Error scraping {request.url} (attempt {attempt + 1}): {e}")
                if attempt == self.config.max_retries:
                    raise RequestError(f"Failed after {self.config.max_retries + 1} attempts: {e}")
            
            if attempt < self.config.max_retries:
                delay = self.config.retry_delay * (self.config.backoff_factor ** attempt)
                await asyncio.sleep(delay)
        
        raise RequestError(f"Max retries exceeded for {request.url}")
    
    async def scrape_batch(
        self,
        requests: List[RequestData],
        processor: Optional[ResponseProcessor] = None,
        max_concurrent: int = 50
    ) -> AsyncGenerator[Any, None]:
        """
        Scrape multiple URLs concurrently.
        
        Args:
            requests: List of request data
            processor: Optional response processor
            max_concurrent: Maximum concurrent requests
            
        Yields:
            Processed response data as requests complete
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(request: RequestData):
            async with semaphore:
                return await self.scrape(request, processor)
        
        tasks = [scrape_with_semaphore(req) for req in requests]
        
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                yield result
            except Exception as e:
                self.logger.error(f"Error in batch scraping: {e}")
                yield e
    
    async def _make_request(self, request: RequestData) -> ResponseData:
        """Make the actual HTTP request."""
        if not self.session:
            raise AsyncScraperError("Session not initialized")
        
        headers = dict(self.config.default_headers)
        if request.headers:
            headers.update(request.headers)
        
        async with self.session.request(
            method=request.method,
            url=request.url,
            headers=headers,
            params=request.params,
            data=request.data
        ) as response:
            content = await response.read()
            text = await response.text()
            
            return ResponseData(
                url=str(response.url),
                status_code=response.status,
                headers=dict(response.headers),
                content=content,
                text=text,
                request_metadata=request.metadata
            )


class ScrapingSession:
    """
    High-level scraping session that manages multiple scrapers and provides
    convenient methods for common scraping patterns.
    """
    
    def __init__(self, config: Optional[ScrapingConfig] = None):
        self.config = config or ScrapingConfig()
        self.scraper: Optional[AsyncScraper] = None
    
    async def __aenter__(self):
        self.scraper = AsyncScraper(self.config)
        await self.scraper.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.scraper:
            await self.scraper.close()
    
    async def get(self, url: str, **kwargs) -> ResponseData:
        """Convenience method for GET requests."""
        request = RequestData(url=url, method='GET', **kwargs)
        return await self.scraper.scrape(request)
    
    async def post(self, url: str, data: Any = None, **kwargs) -> ResponseData:
        """Convenience method for POST requests."""
        request = RequestData(url=url, method='POST', data=data, **kwargs)
        return await self.scraper.scrape(request)
    
    async def get_many(self, urls: List[str], **kwargs) -> AsyncGenerator[ResponseData, None]:
        """Convenience method for scraping multiple URLs."""
        requests = [RequestData(url=url, method='GET') for url in urls]
        async for result in self.scraper.scrape_batch(requests):
            yield result


# Example usage and testing
async def main():
    """Example usage of the async scraper architecture."""
    config = ScrapingConfig(
        requests_per_second=5.0,
        max_retries=2,
        timeout=10
    )
    
    async with ScrapingSession(config) as session:
        # Single request example
        try:
            response = await session.get("https://httpbin.org/json")
            print(f"Status: {response.status_code}")
            print(f"Response time: {response.response_time:.2f}s")
            print(f"Content length: {len(response.content)} bytes")
        except Exception as e:
            print(f"Error: {e}")
        
        # Batch requests example
        urls = [
            "https://httpbin.org/delay/1",
            "https://httpbin.org/delay/2", 
            "https://httpbin.org/json"
        ]
        
        async for response in session.get_many(urls):
            if isinstance(response, Exception):
                print(f"Error: {response}")
            else:
                print(f"Scraped {response.url}: {response.status_code}")


if __name__ == "__main__":
    asyncio.run(main())