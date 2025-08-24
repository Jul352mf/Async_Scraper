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


class WebClient:
    """Async web client with rate limiting, caching, and retry logic."""
    
    def __init__(self, config: Config):
        """Initialize the web client."""
        self.config = config
        self.logger = get_logger("web_client")
        self.cache_manager = CacheManager()
        self.rate_limiter = get_domain_rate_limiter()
        
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
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def fetch_page(self, url: str, domain: str) -> Optional[Dict[str, Any]]:
        """Fetch a single page with rate limiting and caching."""
        # Check cache first
        cache_key = f"page:{url}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            self.logger.debug("Cache hit for page", url=url)
            return cached_result
        
        # Apply rate limiting
        await self.rate_limiter.acquire(domain)
        
        session = await self._get_session()
        
        try:
            self.logger.debug("Fetching page", url=url)
            
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    content_type = response.headers.get('Content-Type', '')
                    
                    result = {
                        'url': url,
                        'content': content,
                        'status_code': response.status,
                        'content_type': content_type,
                        'headers': dict(response.headers),
                        'fetched_at': time.time()
                    }
                    
                    # Cache successful responses
                    await self.cache_manager.set(cache_key, result, ttl=3600)  # 1 hour TTL
                    
                    # Record success for rate limiting
                    await self.rate_limiter.record_success(domain)
                    
                    self.logger.debug("Page fetched successfully", 
                                    url=url, 
                                    content_length=len(content))
                    
                    return result
                    
                else:
                    # Record failure for rate limiting
                    await self.rate_limiter.record_failure(domain, response.status)
                    
                    self.logger.warning("HTTP error fetching page", 
                                      url=url, 
                                      status_code=response.status)
                    return None
                    
        except asyncio.TimeoutError:
            await self.rate_limiter.record_failure(domain)
            self.logger.error("Timeout fetching page", url=url)
            return None
        except Exception as e:
            await self.rate_limiter.record_failure(domain)
            self.logger.error("Error fetching page", url=url, error=str(e))
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