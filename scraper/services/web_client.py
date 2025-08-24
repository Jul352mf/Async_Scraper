"""Web client for making HTTP requests with rate limiting and caching."""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import time
import random

from scraper.core.config import Config
from scraper.core.logger import get_logger
from scraper.core.cache.cache_utils import CacheManager
from scraper.core.utils.rate_limit import RateLimiter, get_domain_rate_limiter
from scraper.core.proxy import ProxyManager, ProxyConfig, ProxyRotationStrategy


class WebClient:
    """Async web client with rate limiting, caching, and proxy support."""
    
    def __init__(self, config: Config):
        """Initialize the web client."""
        self.config = config
        self.logger = get_logger("web_client")
        self.cache_manager = CacheManager()
        self.rate_limiter = get_domain_rate_limiter()
        
        # Initialize proxy manager if enabled
        self._proxy_manager: Optional[ProxyManager] = None
        if config.proxy.enabled and config.proxy.proxy_urls:
            from scraper.core.proxy.models import ProxyConfig as ProxyConfigModel
            proxy_config = ProxyConfigModel(**config.proxy.model_dump())
            self._proxy_manager = ProxyManager.from_urls(config.proxy.proxy_urls, proxy_config)
        
        # HTTP session will be created on first use
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.scraping.timeout)
            connector = aiohttp.TCPConnector(
                limit=self.config.concurrency.max_concurrent_per_domain,
                limit_per_host=self.config.concurrency.max_concurrent_per_domain
            )
            
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': random.choice(self.config.scraping.user_agents)
                }
            )
        
        return self._session
    
    async def initialize(self) -> None:
        """Initialize the web client and proxy manager."""
        if self._proxy_manager:
            await self._proxy_manager.initialize()
            self.logger.info("Initialized proxy manager with proxies", count=len(self._proxy_manager.list_proxies()))
    
    async def close(self) -> None:
        """Close the HTTP session and proxy manager."""
        if self._session and not self._session.closed:
            await self._session.close()
        
        if self._proxy_manager:
            await self._proxy_manager.shutdown()
    
    async def fetch_page(self, url: str, domain: str, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Fetch a single page with rate limiting, caching, and proxy support."""
        # Check cache first
        cache_key = f"page:{url}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            self.logger.debug("Cache hit for page", url=url)
            return cached_result
        
        # Apply rate limiting
        await self.rate_limiter.acquire(domain)
        
        session = await self._get_session()
        
        # Get proxy if enabled
        proxy = None
        proxy_url = None
        if self._proxy_manager:
            proxy = await self._proxy_manager.get_next_proxy()
            if proxy:
                if proxy.username and proxy.password:
                    proxy_url = f"{proxy.effective_proxy_type.value}://{proxy.username}:{proxy.password}@{proxy.effective_host}:{proxy.effective_port}"
                else:
                    proxy_url = f"{proxy.effective_proxy_type.value}://{proxy.effective_host}:{proxy.effective_port}"
                self.logger.debug("Using proxy for request", url=url, proxy_id=proxy.id, proxy_host=proxy.effective_host)
        
        max_retries = self.config.concurrency.retry_max_attempts
        
        try:
            self.logger.debug("Fetching page", url=url, proxy_used=proxy_url is not None)
            
            # Make request with or without proxy
            request_kwargs = {'url': url}
            if proxy_url:
                request_kwargs['proxy'] = proxy_url
            
            async with session.get(**request_kwargs) as response:
                if response.status == 200:
                    content = await response.text()
                    content_type = response.headers.get('Content-Type', '')
                    
                    result = {
                        'url': url,
                        'content': content,
                        'status_code': response.status,
                        'content_type': content_type,
                        'headers': dict(response.headers),
                        'fetched_at': time.time(),
                        'proxy_used': proxy.id if proxy else None
                    }
                    
                    # Cache successful responses
                    await self.cache_manager.set(cache_key, result, ttl=3600)  # 1 hour TTL
                    
                    # Record success for rate limiting and proxy
                    await self.rate_limiter.record_success(domain)
                    if proxy:
                        proxy.update_health(success=True)
                    
                    self.logger.debug("Page fetched successfully", 
                                    url=url, 
                                    content_length=len(content),
                                    proxy_used=proxy.id if proxy else None)
                    
                    return result
                    
                else:
                    # Record failure for rate limiting and proxy
                    await self.rate_limiter.record_failure(domain, response.status)
                    if proxy:
                        proxy.update_health(success=False, error=f"HTTP {response.status}")
                    
                    self.logger.warning("HTTP error fetching page", 
                                      url=url, 
                                      status_code=response.status,
                                      proxy_used=proxy.id if proxy else None)
                    
                    # Retry with different proxy or without proxy if enabled
                    if retry_count < max_retries and self.config.proxy.fallback_to_direct:
                        return await self.fetch_page(url, domain, retry_count + 1)
                    
                    return None
                    
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            await self.rate_limiter.record_failure(domain)
            if proxy:
                proxy.update_health(success=False, error=str(e))
            
            self.logger.error("Error fetching page", 
                            url=url, 
                            error=str(e),
                            proxy_used=proxy.id if proxy else None)
            
            # Retry with different proxy or without proxy if enabled
            if retry_count < max_retries:
                if self._proxy_manager and retry_count == 0:
                    # Try with a different proxy first
                    return await self.fetch_page(url, domain, retry_count + 1)
                elif self.config.proxy.fallback_to_direct and retry_count < max_retries:
                    # Fallback to direct connection
                    self.logger.debug("Falling back to direct connection", url=url)
                    return await self.fetch_page(url, domain, retry_count + 1)
            
            return None
        except Exception as e:
            await self.rate_limiter.record_failure(domain)
            if proxy:
                proxy.update_health(success=False, error=str(e))
            self.logger.error("Unexpected error fetching page", url=url, error=str(e))
            return None
    
    async def fetch_domain_pages(self, domain: str) -> List[Dict[str, Any]]:
        """Fetch multiple pages for a domain."""
        urls_to_try = self._generate_urls_for_domain(domain)
        pages = []
        
        self.logger.debug("Fetching pages for domain", 
                         domain=domain, 
                         urls_count=len(urls_to_try))
        
        # Limit concurrent requests per domain
        semaphore = asyncio.Semaphore(self.config.concurrency.max_concurrent_per_domain)
        
        async def fetch_with_semaphore(url: str) -> Optional[Dict[str, Any]]:
            async with semaphore:
                return await self.fetch_page(url, domain)
        
        # Fetch pages concurrently
        tasks = [fetch_with_semaphore(url) for url in urls_to_try]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        for result in results:
            if isinstance(result, dict) and result is not None:
                pages.append(result)
            elif isinstance(result, Exception):
                self.logger.debug("Failed to fetch page", error=str(result))
        
        self.logger.info("Fetched pages for domain", 
                        domain=domain, 
                        successful_pages=len(pages),
                        total_attempts=len(urls_to_try))
        
        return pages
    
    def _generate_urls_for_domain(self, domain: str) -> List[str]:
        """Generate URLs to try for a domain."""
        # Ensure domain has protocol
        if not domain.startswith(('http://', 'https://')):
            domain = f"https://{domain}"
        
        # Parse domain to get base URL
        parsed = urlparse(domain)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Common paths that often contain contact information
        common_paths = [
            '/',  # Homepage
            '/contact',
            '/contact-us',
            '/about',
            '/about-us',
            '/team',
            '/staff',
            '/people',
            '/management',
            '/leadership',
            '/executives',
            '/company',
            '/info',
            '/support',
            '/help',
        ]
        
        urls = []
        for path in common_paths:
            url = urljoin(base_domain, path)
            urls.append(url)
        
        # Limit to max crawl depth worth of URLs
        max_urls = min(len(urls), self.config.scraping.max_crawl_depth * 3)
        return urls[:max_urls]
    
    async def check_robots_txt(self, domain: str) -> bool:
        """Check if domain allows crawling via robots.txt."""
        if not self.config.scraping.respect_robots_txt:
            return True
        
        try:
            # Ensure domain has protocol
            if not domain.startswith(('http://', 'https://')):
                domain = f"https://{domain}"
            
            parsed = urlparse(domain)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            robots_info = await self.fetch_page(robots_url, parsed.netloc)
            
            if robots_info:
                content = robots_info['content'].lower()
                # Simple robots.txt check - look for disallow rules
                # In a production system, you'd want a proper robots.txt parser
                if 'user-agent: *' in content and 'disallow: /' in content:
                    self.logger.info("Robots.txt disallows crawling", domain=domain)
                    return False
            
            return True
            
        except Exception as e:
            self.logger.debug("Could not check robots.txt", domain=domain, error=str(e))
            # If we can't check robots.txt, assume it's OK to crawl
            return True