"""
Proxy health checking system for monitoring proxy availability and performance.
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

import aiohttp
from scraper.core.logger import get_logger
from .models import Proxy, ProxyStatus, ProxyConfig

logger = get_logger(__name__)


class ProxyHealthChecker:
    """Health checker for monitoring proxy availability and performance."""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the health checking background task."""
        if self._running:
            return
        
        self._running = True
        self._check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Started proxy health checker")
    
    async def stop(self) -> None:
        """Stop the health checking background task."""
        if not self._running:
            return
        
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped proxy health checker")
    
    async def _health_check_loop(self) -> None:
        """Main health check loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
    
    async def check_proxy(self, proxy: Proxy) -> bool:
        """Check health of a single proxy."""
        if not proxy.enabled:
            return False
        
        proxy.health.status = ProxyStatus.CHECKING
        start_time = time.time()
        
        try:
            success = await self._perform_health_check(proxy)
            response_time = time.time() - start_time
            
            proxy.update_health(
                success=success,
                response_time=response_time if success else None
            )
            
            if success:
                logger.debug(
                    "Proxy health check passed", 
                    proxy_id=proxy.id,
                    response_time=response_time
                )
            else:
                logger.warning(
                    "Proxy health check failed", 
                    proxy_id=proxy.id,
                    consecutive_failures=proxy.health.consecutive_failures
                )
            
            return success
            
        except Exception as e:
            response_time = time.time() - start_time
            proxy.update_health(
                success=False,
                error=str(e)
            )
            
            logger.error(
                "Proxy health check error", 
                proxy_id=proxy.id,
                error=str(e),
                consecutive_failures=proxy.health.consecutive_failures
            )
            return False
    
    async def _perform_health_check(self, proxy: Proxy) -> bool:
        """Perform actual HTTP request through proxy."""
        try:
            timeout = aiohttp.ClientTimeout(total=self.config.health_check_timeout)
            connector = aiohttp.TCPConnector()
            
            proxy_url = None
            if proxy.username and proxy.password:
                proxy_url = f"{proxy.effective_proxy_type.value}://{proxy.username}:{proxy.password}@{proxy.effective_host}:{proxy.effective_port}"
            else:
                proxy_url = f"{proxy.effective_proxy_type.value}://{proxy.effective_host}:{proxy.effective_port}"
            
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            ) as session:
                async with session.get(
                    self.config.health_check_url,
                    proxy=proxy_url
                ) as response:
                    # Consider 2xx status codes as healthy
                    return 200 <= response.status < 300
                    
        except Exception as e:
            logger.debug("Health check request failed", proxy_id=proxy.id, error=str(e))
            return False
    
    async def check_proxies(self, proxies: List[Proxy]) -> Dict[str, bool]:
        """Check health of multiple proxies concurrently."""
        if not proxies:
            return {}
        
        # Limit concurrent health checks to avoid overwhelming
        semaphore = asyncio.Semaphore(min(10, len(proxies)))
        
        async def check_with_semaphore(proxy: Proxy) -> tuple[str, bool]:
            async with semaphore:
                result = await self.check_proxy(proxy)
                return proxy.id, result
        
        tasks = [check_with_semaphore(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health_results = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error("Health check task failed", error=str(result))
            else:
                proxy_id, is_healthy = result
                health_results[proxy_id] = is_healthy
        
        return health_results
    
    def should_check_proxy(self, proxy: Proxy) -> bool:
        """Determine if proxy needs health check."""
        if not proxy.enabled:
            return False
        
        # Always check if never checked before
        if not proxy.health.last_checked:
            return True
        
        # Check if enough time has passed since last check
        time_since_check = datetime.utcnow() - proxy.health.last_checked
        return time_since_check.total_seconds() >= self.config.health_check_interval
    
    def unblacklist_proxies(self, proxies: List[Proxy]) -> List[Proxy]:
        """Unblacklist proxies that have been blacklisted for too long."""
        unblacklisted = []
        current_time = datetime.utcnow()
        
        for proxy in proxies:
            if proxy.health.status == ProxyStatus.BLACKLISTED:
                if proxy.health.last_checked:
                    time_since_blacklist = current_time - proxy.health.last_checked
                    if time_since_blacklist.total_seconds() >= self.config.blacklist_duration:
                        proxy.health.status = ProxyStatus.UNKNOWN
                        proxy.health.consecutive_failures = 0
                        unblacklisted.append(proxy)
                        logger.info("Unblacklisted proxy for retry", proxy_id=proxy.id)
        
        return unblacklisted