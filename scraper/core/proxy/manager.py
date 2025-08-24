"""
Main proxy manager that coordinates all proxy-related functionality.
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from scraper.core.logger import get_logger
from .models import Proxy, ProxyConfig, ProxyRotationStrategy
from .rotation import ProxyRotator
from .health_checker import ProxyHealthChecker

logger = get_logger(__name__)


class ProxyManager:
    """Main proxy manager that coordinates proxy operations."""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self._proxies: Dict[str, Proxy] = {}
        self._rotator: Optional[ProxyRotator] = None
        self._health_checker = ProxyHealthChecker(config)
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the proxy manager."""
        if self._initialized:
            return
        
        if self.config.enabled:
            await self._health_checker.start()
            logger.info("Proxy manager initialized")
        else:
            logger.info("Proxy manager initialized (disabled)")
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Shutdown the proxy manager."""
        if not self._initialized:
            return
        
        await self._health_checker.stop()
        self._initialized = False
        logger.info("Proxy manager shutdown")
    
    def add_proxy(self, proxy: Proxy) -> None:
        """Add a proxy to the manager."""
        self._proxies[proxy.id] = proxy
        self._update_rotator()
        logger.info("Added proxy", proxy_id=proxy.id, host=proxy.effective_host)
    
    def add_proxies(self, proxies: List[Proxy]) -> None:
        """Add multiple proxies to the manager."""
        for proxy in proxies:
            self._proxies[proxy.id] = proxy
        
        self._update_rotator()
        logger.info("Added proxies", count=len(proxies))
    
    def remove_proxy(self, proxy_id: str) -> bool:
        """Remove a proxy from the manager."""
        if proxy_id in self._proxies:
            proxy = self._proxies.pop(proxy_id)
            self._update_rotator()
            logger.info("Removed proxy", proxy_id=proxy_id, host=proxy.effective_host)
            return True
        return False
    
    def get_proxy(self, proxy_id: str) -> Optional[Proxy]:
        """Get a specific proxy by ID."""
        return self._proxies.get(proxy_id)
    
    def list_proxies(self, enabled_only: bool = False, healthy_only: bool = False) -> List[Proxy]:
        """List all proxies with optional filtering."""
        proxies = list(self._proxies.values())
        
        if enabled_only:
            proxies = [p for p in proxies if p.enabled]
        
        if healthy_only:
            proxies = [p for p in proxies if p.health.is_healthy]
        
        return proxies
    
    def enable_proxy(self, proxy_id: str) -> bool:
        """Enable a proxy."""
        proxy = self._proxies.get(proxy_id)
        if proxy:
            proxy.enabled = True
            self._update_rotator()
            logger.info("Enabled proxy", proxy_id=proxy_id)
            return True
        return False
    
    def disable_proxy(self, proxy_id: str) -> bool:
        """Disable a proxy."""
        proxy = self._proxies.get(proxy_id)
        if proxy:
            proxy.enabled = False
            self._update_rotator()
            logger.info("Disabled proxy", proxy_id=proxy_id)
            return True
        return False
    
    def update_proxy(self, proxy_id: str, updates: Dict[str, Any]) -> bool:
        """Update proxy configuration."""
        proxy = self._proxies.get(proxy_id)
        if not proxy:
            return False
        
        # Update allowed fields
        allowed_fields = ['description', 'tags', 'country', 'region', 'enabled']
        for field, value in updates.items():
            if field in allowed_fields and hasattr(proxy, field):
                setattr(proxy, field, value)
        
        if 'enabled' in updates:
            self._update_rotator()
        
        logger.info("Updated proxy", proxy_id=proxy_id, updates=updates)
        return True
    
    async def get_next_proxy(self) -> Optional[Proxy]:
        """Get the next proxy according to the rotation strategy."""
        if not self.config.enabled or not self._rotator:
            return None
        
        proxy = self._rotator.get_next_proxy()
        if proxy:
            proxy.mark_used()
            logger.debug("Selected proxy for use", proxy_id=proxy.id)
        
        return proxy
    
    async def check_proxy_health(self, proxy_id: str) -> bool:
        """Check health of a specific proxy."""
        proxy = self._proxies.get(proxy_id)
        if not proxy:
            return False
        
        return await self._health_checker.check_proxy(proxy)
    
    async def check_all_proxies_health(self) -> Dict[str, bool]:
        """Check health of all proxies."""
        proxies = list(self._proxies.values())
        return await self._health_checker.check_proxies(proxies)
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """Get proxy statistics."""
        proxies = list(self._proxies.values())
        
        total_proxies = len(proxies)
        enabled_proxies = len([p for p in proxies if p.enabled])
        healthy_proxies = len([p for p in proxies if p.health.is_healthy])
        
        # Calculate average response time
        response_times = [
            p.health.response_time for p in proxies 
            if p.health.response_time is not None
        ]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Get status distribution
        status_counts = {}
        for proxy in proxies:
            status = proxy.health.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_proxies": total_proxies,
            "enabled_proxies": enabled_proxies,
            "healthy_proxies": healthy_proxies,
            "average_response_time": avg_response_time,
            "status_distribution": status_counts,
            "rotation_strategy": self.config.rotation_strategy.value,
        }
    
    def set_rotation_strategy(self, strategy: ProxyRotationStrategy) -> None:
        """Change the proxy rotation strategy."""
        self.config.rotation_strategy = strategy
        if self._rotator:
            self._rotator.set_strategy(strategy)
        logger.info("Changed rotation strategy", strategy=strategy.value)
    
    def set_geographic_preference(self, country: Optional[str]) -> None:
        """Set geographic preference for proxy selection."""
        self.config.geographic_preference = country
        if self._rotator:
            self._rotator.set_geographic_preference(country)
        logger.info("Set geographic preference", country=country)
    
    def _update_rotator(self) -> None:
        """Update the proxy rotator with current proxies."""
        proxies = list(self._proxies.values())
        
        if not self._rotator:
            self._rotator = ProxyRotator(proxies, self.config.rotation_strategy)
        else:
            self._rotator.update_proxies(proxies)
    
    @classmethod
    def from_urls(cls, urls: List[str], config: ProxyConfig) -> 'ProxyManager':
        """Create proxy manager from list of proxy URLs."""
        manager = cls(config)
        
        proxies = []
        for url in urls:
            try:
                proxy = Proxy(url=url)
                proxies.append(proxy)
                logger.debug("Created proxy from URL", url=url, proxy_id=proxy.id)
            except Exception as e:
                logger.error("Failed to create proxy from URL", url=url, error=str(e))
        
        if proxies:
            manager.add_proxies(proxies)
        
        return manager