"""In-memory LRU cache implementation using cachetools."""

import asyncio
import time
from typing import Any, Optional

from cachetools import TTLCache

from scraper.core.config import get_config
from scraper.core.logger import get_logger, LoggerMixin

logger = get_logger(__name__)


class AsyncLRUCache(LoggerMixin):
    """Thread-safe async LRU cache with TTL support."""
    
    def __init__(self, 
                 max_size: Optional[int] = None,
                 ttl: Optional[int] = None,
                 name: str = "AsyncLRUCache"):
        """
        Initialize async LRU cache.
        
        Args:
            max_size: Maximum number of entries (from config if None)
            ttl: Time to live in seconds (from config if None)
            name: Cache instance name for logging
        """
        super().__init__()
        config = get_config()
        
        self.max_size = max_size or config.cache.l1_max_size
        self.ttl = ttl or config.cache.l1_ttl
        self.name = name
        
        # Use TTLCache from cachetools
        self._cache = TTLCache(maxsize=self.max_size, ttl=self.ttl)
        self._lock = asyncio.Lock()
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0,
            'errors': 0
        }
        
        self.log_info(f"Initialized {self.name}",
                     max_size=self.max_size,
                     ttl=self.ttl)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            try:
                value = self._cache[key]
                self._stats['hits'] += 1
                
                self.log_debug(f"Cache hit for key: {key}",
                              cache=self.name,
                              key=key)
                
                return value
                
            except KeyError:
                self._stats['misses'] += 1
                
                self.log_debug(f"Cache miss for key: {key}",
                              cache=self.name,
                              key=key)
                
                return None
            except Exception as e:
                self._stats['errors'] += 1
                self.log_error(f"Cache get error for key: {key}",
                              cache=self.name,
                              key=key,
                              error=str(e))
                return None
    
    async def set(self, key: str, value: Any) -> bool:
        """Set value in cache."""
        async with self._lock:
            try:
                # Check if this will cause eviction
                if len(self._cache) >= self.max_size and key not in self._cache:
                    self._stats['evictions'] += 1
                
                self._cache[key] = value
                self._stats['sets'] += 1
                
                self.log_debug(f"Cache set for key: {key}",
                              cache=self.name,
                              key=key,
                              cache_size=len(self._cache))
                
                return True
                
            except Exception as e:
                self._stats['errors'] += 1
                self.log_error(f"Cache set error for key: {key}",
                              cache=self.name,
                              key=key,
                              error=str(e))
                return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        async with self._lock:
            try:
                if key in self._cache:
                    del self._cache[key]
                    self._stats['deletes'] += 1
                    
                    self.log_debug(f"Cache delete for key: {key}",
                                  cache=self.name,
                                  key=key)
                    
                    return True
                return False
                
            except Exception as e:
                self._stats['errors'] += 1
                self.log_error(f"Cache delete error for key: {key}",
                              cache=self.name,
                              key=key,
                              error=str(e))
                return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        async with self._lock:
            return key in self._cache
    
    async def clear(self) -> bool:
        """Clear all entries from cache."""
        async with self._lock:
            try:
                size_before = len(self._cache)
                self._cache.clear()
                
                self.log_info(f"Cache cleared",
                             cache=self.name,
                             entries_removed=size_before)
                
                return True
                
            except Exception as e:
                self._stats['errors'] += 1
                self.log_error(f"Cache clear error",
                              cache=self.name,
                              error=str(e))
                return False
    
    async def size(self) -> int:
        """Get current cache size."""
        async with self._lock:
            return len(self._cache)
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            **self._stats,
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'current_size': len(self._cache),
            'max_size': self.max_size,
            'ttl': self.ttl,
            'name': self.name
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = {key: 0 for key in self._stats}
        self.log_info(f"Cache statistics reset", cache=self.name)


class CacheDecorator:
    """Decorator for caching function results."""
    
    def __init__(self, 
                 cache: Optional[AsyncLRUCache] = None,
                 ttl: Optional[int] = None,
                 key_prefix: str = ""):
        """
        Initialize cache decorator.
        
        Args:
            cache: Cache instance (creates default if None)
            ttl: TTL for cached values
            key_prefix: Prefix for cache keys
        """
        self.cache = cache or AsyncLRUCache(name="DecoratorCache", ttl=ttl)
        self.key_prefix = key_prefix
    
    def __call__(self, func):
        """Apply caching to function."""
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_parts = [self.key_prefix, func.__name__]
            
            # Add args to key
            if args:
                key_parts.extend(str(arg) for arg in args)
            
            # Add kwargs to key
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                key_parts.extend(f"{k}={v}" for k, v in sorted_kwargs)
            
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_value = await self.cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await self.cache.set(cache_key, result)
            
            return result
        
        return wrapper


def cached(ttl: Optional[int] = None, key_prefix: str = ""):
    """
    Decorator for caching async function results.
    
    Usage:
        @cached(ttl=300, key_prefix="api")
        async def fetch_data(url):
            return await make_request(url)
    """
    return CacheDecorator(ttl=ttl, key_prefix=key_prefix)


# Global L1 cache instance
_l1_cache: Optional[AsyncLRUCache] = None


def get_l1_cache() -> AsyncLRUCache:
    """Get global L1 cache instance."""
    global _l1_cache
    if _l1_cache is None:
        config = get_config()
        if config.cache.l1_enabled:
            _l1_cache = AsyncLRUCache(
                max_size=config.cache.l1_max_size,
                ttl=config.cache.l1_ttl,
                name="GlobalL1Cache"
            )
        else:
            # Create a dummy cache that doesn't actually cache
            class DummyCache:
                async def get(self, key): return None
                async def set(self, key, value): return True
                async def delete(self, key): return False
                async def exists(self, key): return False
                async def clear(self): return True
                async def size(self): return 0
                def get_stats(self): return {}
                def reset_stats(self): pass
            
            _l1_cache = DummyCache()
    
    return _l1_cache