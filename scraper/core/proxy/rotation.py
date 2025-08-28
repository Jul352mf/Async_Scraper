"""
Proxy rotation strategies for load balancing and performance optimization.
"""

import random
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime, timedelta

from scraper.core.logger import get_logger
from .models import Proxy, ProxyRotationStrategy

logger = get_logger(__name__)


class BaseRotator(ABC):
    """Base class for proxy rotation strategies."""
    
    def __init__(self, proxies: List[Proxy]):
        self.proxies = proxies
        self._current_index = 0
    
    @abstractmethod
    def get_next_proxy(self) -> Optional[Proxy]:
        """Get the next proxy according to the rotation strategy."""
        pass
    
    def get_healthy_proxies(self) -> List[Proxy]:
        """Get list of healthy and enabled proxies."""
        return [
            proxy for proxy in self.proxies 
            if proxy.enabled and proxy.health.is_healthy
        ]
    
    def update_proxies(self, proxies: List[Proxy]) -> None:
        """Update the list of available proxies."""
        self.proxies = proxies


class RoundRobinRotator(BaseRotator):
    """Round-robin proxy rotation strategy."""
    
    def get_next_proxy(self) -> Optional[Proxy]:
        """Get next proxy in round-robin order."""
        healthy_proxies = self.get_healthy_proxies()
        
        if not healthy_proxies:
            logger.warning("No healthy proxies available")
            return None
        
        proxy = healthy_proxies[self._current_index % len(healthy_proxies)]
        self._current_index = (self._current_index + 1) % len(healthy_proxies)
        
        logger.debug("Selected proxy via round-robin", proxy_id=proxy.id, host=proxy.effective_host)
        return proxy


class RandomRotator(BaseRotator):
    """Random proxy rotation strategy."""
    
    def get_next_proxy(self) -> Optional[Proxy]:
        """Get random healthy proxy."""
        healthy_proxies = self.get_healthy_proxies()
        
        if not healthy_proxies:
            logger.warning("No healthy proxies available")
            return None
        
        proxy = random.choice(healthy_proxies)
        logger.debug("Selected proxy via random", proxy_id=proxy.id, host=proxy.effective_host)
        return proxy


class LeastUsedRotator(BaseRotator):
    """Least used proxy rotation strategy."""
    
    def get_next_proxy(self) -> Optional[Proxy]:
        """Get the least used healthy proxy."""
        healthy_proxies = self.get_healthy_proxies()
        
        if not healthy_proxies:
            logger.warning("No healthy proxies available")
            return None
        
        # Sort by use count (ascending) and last used time
        proxy = min(
            healthy_proxies,
            key=lambda p: (p.use_count, p.last_used or datetime.min)
        )
        
        logger.debug("Selected proxy via least-used", proxy_id=proxy.id, use_count=proxy.use_count)
        return proxy


class FastestRotator(BaseRotator):
    """Fastest response time proxy rotation strategy."""
    
    def get_next_proxy(self) -> Optional[Proxy]:
        """Get the proxy with fastest response time."""
        healthy_proxies = self.get_healthy_proxies()
        
        if not healthy_proxies:
            logger.warning("No healthy proxies available")
            return None
        
        # Filter proxies that have response time data
        proxies_with_timing = [
            p for p in healthy_proxies 
            if p.health.response_time is not None
        ]
        
        if not proxies_with_timing:
            # Fallback to random if no timing data available
            proxy = random.choice(healthy_proxies)
            logger.debug("Selected proxy via fastest (fallback to random)", proxy_id=proxy.id)
            return proxy
        
        # Get proxy with minimum response time
        proxy = min(proxies_with_timing, key=lambda p: p.health.response_time)
        logger.debug(
            "Selected proxy via fastest", 
            proxy_id=proxy.id, 
            response_time=proxy.health.response_time
        )
        return proxy


class GeographicRotator(BaseRotator):
    """Geographic preference proxy rotation strategy."""
    
    def __init__(self, proxies: List[Proxy], preferred_country: Optional[str] = None):
        super().__init__(proxies)
        self.preferred_country = preferred_country
    
    def get_next_proxy(self) -> Optional[Proxy]:
        """Get proxy with geographic preference."""
        healthy_proxies = self.get_healthy_proxies()
        
        if not healthy_proxies:
            logger.warning("No healthy proxies available")
            return None
        
        # If preferred country is set, try to get proxy from that country
        if self.preferred_country:
            preferred_proxies = [
                p for p in healthy_proxies 
                if p.country and p.country.lower() == self.preferred_country.lower()
            ]
            
            if preferred_proxies:
                proxy = random.choice(preferred_proxies)
                logger.debug(
                    "Selected proxy via geographic preference", 
                    proxy_id=proxy.id, 
                    country=proxy.country
                )
                return proxy
        
        # Fallback to random selection
        proxy = random.choice(healthy_proxies)
        logger.debug("Selected proxy via geographic (fallback to random)", proxy_id=proxy.id)
        return proxy


class ProxyRotator:
    """Main proxy rotator that manages different rotation strategies."""
    
    def __init__(self, proxies: List[Proxy], strategy: ProxyRotationStrategy = ProxyRotationStrategy.ROUND_ROBIN):
        self.proxies = proxies
        self.strategy = strategy
        self._rotator = self._create_rotator()
    
    def _create_rotator(self) -> BaseRotator:
        """Create appropriate rotator based on strategy."""
        if self.strategy == ProxyRotationStrategy.ROUND_ROBIN:
            return RoundRobinRotator(self.proxies)
        elif self.strategy == ProxyRotationStrategy.RANDOM:
            return RandomRotator(self.proxies)
        elif self.strategy == ProxyRotationStrategy.LEAST_USED:
            return LeastUsedRotator(self.proxies)
        elif self.strategy == ProxyRotationStrategy.FASTEST:
            return FastestRotator(self.proxies)
        elif self.strategy == ProxyRotationStrategy.GEOGRAPHIC:
            return GeographicRotator(self.proxies)
        else:
            logger.warning("Unknown rotation strategy, falling back to round-robin", strategy=self.strategy)
            return RoundRobinRotator(self.proxies)
    
    def get_next_proxy(self) -> Optional[Proxy]:
        """Get next proxy according to configured strategy."""
        return self._rotator.get_next_proxy()
    
    def update_proxies(self, proxies: List[Proxy]) -> None:
        """Update the list of available proxies."""
        self.proxies = proxies
        self._rotator.update_proxies(proxies)
    
    def set_strategy(self, strategy: ProxyRotationStrategy) -> None:
        """Change rotation strategy."""
        if strategy != self.strategy:
            self.strategy = strategy
            self._rotator = self._create_rotator()
            logger.info("Changed proxy rotation strategy", strategy=strategy.value)
    
    def set_geographic_preference(self, country: Optional[str]) -> None:
        """Set geographic preference for geographic rotator."""
        if isinstance(self._rotator, GeographicRotator):
            self._rotator.preferred_country = country
            logger.info("Updated geographic preference", country=country)