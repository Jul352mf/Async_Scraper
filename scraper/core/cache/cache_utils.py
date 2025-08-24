"""Unified cache interface supporting multiple cache layers."""

from typing import Any, Optional, List, Dict

from scraper.core.cache.lru_cache import get_l1_cache
from scraper.core.cache.redis_cache import get_l2_cache
from scraper.core.config import get_config
from scraper.core.logger import get_logger, LoggerMixin

logger = get_logger(__name__)


class CacheManager(LoggerMixin):
    """Multi-layer cache manager (L1/L2/L3) with cache-aside pattern."""
    
    def __init__(self):
        """Initialize cache manager."""
        super().__init__()
        self.config = get_config()
        
        # Initialize cache layers
        self.l1_cache = get_l1_cache() if self.config.cache.l1_enabled else None
        self.l2_cache = get_l2_cache() if self.config.cache.l2_enabled else None
        self.l3_cache = None  # TODO: PostgreSQL cache for persistence
        
        # Statistics
        self._stats = {
            'l1_hits': 0,
            'l2_hits': 0,
            'l3_hits': 0,
            'total_misses': 0,
            'total_sets': 0,
            'total_errors': 0
        }
        
        self.log_info("CacheManager initialized",
                     l1_enabled=self.config.cache.l1_enabled,
                     l2_enabled=self.config.cache.l2_enabled,
                     l3_enabled=self.config.cache.l3_enabled)
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache, checking L1 -> L2 -> L3 in order.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        # Try L1 cache first
        if self.l1_cache:
            try:
                value = await self.l1_cache.get(key)
                if value is not None:
                    self._stats['l1_hits'] += 1
                    self.log_debug(f"L1 cache hit for key: {key}", key=key, layer="L1")
                    return value
            except Exception as e:
                self._stats['total_errors'] += 1
                self.log_error(f"L1 cache error for key: {key}", key=key, error=str(e))
        
        # Try L2 cache
        if self.l2_cache:
            try:
                value = await self.l2_cache.get(key)
                if value is not None:
                    self._stats['l2_hits'] += 1
                    self.log_debug(f"L2 cache hit for key: {key}", key=key, layer="L2")
                    
                    # Populate L1 cache for faster future access
                    if self.l1_cache:
                        await self.l1_cache.set(key, value)
                    
                    return value
            except Exception as e:
                self._stats['total_errors'] += 1
                self.log_error(f"L2 cache error for key: {key}", key=key, error=str(e))
        
        # Try L3 cache (PostgreSQL) - TODO: implement
        if self.l3_cache:
            try:
                value = await self.l3_cache.get(key)
                if value is not None:
                    self._stats['l3_hits'] += 1
                    self.log_debug(f"L3 cache hit for key: {key}", key=key, layer="L3")
                    
                    # Populate L1 and L2 caches
                    if self.l1_cache:
                        await self.l1_cache.set(key, value)
                    if self.l2_cache:
                        await self.l2_cache.set(key, value)
                    
                    return value
            except Exception as e:
                self._stats['total_errors'] += 1
                self.log_error(f"L3 cache error for key: {key}", key=key, error=str(e))
        
        # Cache miss
        self._stats['total_misses'] += 1
        self.log_debug(f"Cache miss for key: {key}", key=key)
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in all available cache layers.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional override)
            
        Returns:
            True if at least one cache layer succeeded
        """
        success_count = 0
        self._stats['total_sets'] += 1
        
        # Set in L1 cache
        if self.l1_cache:
            try:
                if await self.l1_cache.set(key, value):
                    success_count += 1
                    self.log_debug(f"L1 cache set for key: {key}", key=key, layer="L1")
            except Exception as e:
                self._stats['total_errors'] += 1
                self.log_error(f"L1 cache set error for key: {key}", key=key, error=str(e))
        
        # Set in L2 cache
        if self.l2_cache:
            try:
                if await self.l2_cache.set(key, value, ttl):
                    success_count += 1
                    self.log_debug(f"L2 cache set for key: {key}", key=key, layer="L2")
            except Exception as e:
                self._stats['total_errors'] += 1
                self.log_error(f"L2 cache set error for key: {key}", key=key, error=str(e))
        
        # Set in L3 cache - TODO: implement
        if self.l3_cache:
            try:
                if await self.l3_cache.set(key, value, ttl):
                    success_count += 1
                    self.log_debug(f"L3 cache set for key: {key}", key=key, layer="L3")
            except Exception as e:
                self._stats['total_errors'] += 1
                self.log_error(f"L3 cache set error for key: {key}", key=key, error=str(e))
        
        return success_count > 0
    
    async def delete(self, key: str) -> bool:
        """Delete key from all cache layers."""
        success_count = 0
        
        # Delete from all layers
        if self.l1_cache:
            try:
                if await self.l1_cache.delete(key):
                    success_count += 1
            except Exception as e:
                self._stats['total_errors'] += 1
                self.log_error(f"L1 cache delete error for key: {key}", key=key, error=str(e))
        
        if self.l2_cache:
            try:
                if await self.l2_cache.delete(key):
                    success_count += 1
            except Exception as e:
                self._stats['total_errors'] += 1
                self.log_error(f"L2 cache delete error for key: {key}", key=key, error=str(e))
        
        if self.l3_cache:
            try:
                if await self.l3_cache.delete(key):
                    success_count += 1
            except Exception as e:
                self._stats['total_errors'] += 1
                self.log_error(f"L3 cache delete error for key: {key}", key=key, error=str(e))
        
        self.log_debug(f"Cache delete for key: {key}", key=key, layers_affected=success_count)
        return success_count > 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in any cache layer."""
        # Check L1 first (fastest)
        if self.l1_cache:
            try:
                if await self.l1_cache.exists(key):
                    return True
            except Exception as e:
                self.log_error(f"L1 cache exists error for key: {key}", key=key, error=str(e))
        
        # Check L2
        if self.l2_cache:
            try:
                if await self.l2_cache.exists(key):
                    return True
            except Exception as e:
                self.log_error(f"L2 cache exists error for key: {key}", key=key, error=str(e))
        
        # Check L3
        if self.l3_cache:
            try:
                if await self.l3_cache.exists(key):
                    return True
            except Exception as e:
                self.log_error(f"L3 cache exists error for key: {key}", key=key, error=str(e))
        
        return False
    
    async def clear_all(self) -> bool:
        """Clear all cache layers."""
        success_count = 0
        
        if self.l1_cache:
            try:
                if await self.l1_cache.clear():
                    success_count += 1
            except Exception as e:
                self.log_error("L1 cache clear error", error=str(e))
        
        if self.l2_cache:
            try:
                if await self.l2_cache.clear():
                    success_count += 1
            except Exception as e:
                self.log_error("L2 cache clear error", error=str(e))
        
        if self.l3_cache:
            try:
                if await self.l3_cache.clear():
                    success_count += 1
            except Exception as e:
                self.log_error("L3 cache clear error", error=str(e))
        
        self.log_info(f"Cache clear completed", layers_cleared=success_count)
        return success_count > 0
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get information about all cache layers."""
        info = {
            'enabled_layers': [],
            'stats': self._stats.copy(),
            'layer_stats': {}
        }
        
        if self.l1_cache:
            info['enabled_layers'].append('L1')
            try:
                info['layer_stats']['L1'] = self.l1_cache.get_stats()
            except Exception as e:
                info['layer_stats']['L1'] = {'error': str(e)}
        
        if self.l2_cache:
            info['enabled_layers'].append('L2')
            try:
                info['layer_stats']['L2'] = self.l2_cache.get_stats()
            except Exception as e:
                info['layer_stats']['L2'] = {'error': str(e)}
        
        if self.l3_cache:
            info['enabled_layers'].append('L3')
            try:
                info['layer_stats']['L3'] = self.l3_cache.get_stats()
            except Exception as e:
                info['layer_stats']['L3'] = {'error': str(e)}
        
        # Calculate overall hit rate
        total_hits = self._stats['l1_hits'] + self._stats['l2_hits'] + self._stats['l3_hits']
        total_requests = total_hits + self._stats['total_misses']
        info['overall_hit_rate'] = total_hits / total_requests if total_requests > 0 else 0
        
        return info
    
    async def warmup(self, data: Dict[str, Any]) -> int:
        """Warm up cache with provided data."""
        warmed_count = 0
        
        for key, value in data.items():
            if await self.set(key, value):
                warmed_count += 1
        
        self.log_info(f"Cache warmup completed", items_warmed=warmed_count)
        return warmed_count


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# Convenience functions for common cache operations
async def cache_get(key: str) -> Optional[Any]:
    """Get value from cache."""
    manager = get_cache_manager()
    return await manager.get(key)


async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Set value in cache."""
    manager = get_cache_manager()
    return await manager.set(key, value, ttl)


async def cache_delete(key: str) -> bool:
    """Delete key from cache."""
    manager = get_cache_manager()
    return await manager.delete(key)


async def cache_exists(key: str) -> bool:
    """Check if key exists in cache."""
    manager = get_cache_manager()
    return await manager.exists(key)


# Cache decorator using the global cache manager
def cache_result(key_prefix: str = "", ttl: Optional[int] = None):
    """
    Decorator to cache function results.
    
    Usage:
        @cache_result(key_prefix="api", ttl=300)
        async def fetch_data(url):
            return await make_request(url)
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Create cache key
            key_parts = [key_prefix, func.__name__]
            
            if args:
                key_parts.extend(str(arg) for arg in args)
            
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                key_parts.extend(f"{k}={v}" for k, v in sorted_kwargs)
            
            cache_key = ":".join(filter(None, key_parts))
            
            # Try to get from cache
            cached_value = await cache_get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator