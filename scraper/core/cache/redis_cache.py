"""Redis cache implementation for L2 caching."""

import asyncio
import json
import pickle
from typing import Any, Optional, Union

from scraper.core.config import get_config
from scraper.core.logger import get_logger, LoggerMixin

logger = get_logger(__name__)

# Check Redis availability without importing
REDIS_AVAILABLE = False  # Temporarily disabled due to aioredis compatibility issues
# try:
#     import importlib
#     importlib.import_module('aioredis')
#     REDIS_AVAILABLE = True
# except ImportError:
#     logger.warning("aioredis not available, Redis caching disabled")


class AsyncRedisCache(LoggerMixin):
    """Async Redis cache for L2 distributed caching."""
    
    def __init__(self, 
                 redis_url: Optional[str] = None,
                 ttl: Optional[int] = None,
                 name: str = "AsyncRedisCache",
                 serializer: str = "json"):
        """
        Initialize async Redis cache.
        
        Args:
            redis_url: Redis connection URL (from config if None)
            ttl: Time to live in seconds (from config if None)
            name: Cache instance name for logging
            serializer: Serialization method ("json" or "pickle")
        """
        super().__init__()
        config = get_config()
        
        self.redis_url = redis_url or config.cache.l2_redis_url
        self.ttl = ttl or config.cache.l2_ttl
        self.name = name
        self.serializer = serializer
        
        self._redis: Optional[aioredis.Redis] = None
        self._connected = False
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0,
            'connection_errors': 0
        }
        
        self.log_info(f"Initialized {self.name}",
                     redis_url=self.redis_url,
                     ttl=self.ttl,
                     serializer=self.serializer)
    
    async def connect(self) -> bool:
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            self.log_error("aioredis not available, cannot connect to Redis")
            return False
            
        try:
            import aioredis  # Import only when needed
            self._redis = aioredis.from_url(
                self.redis_url,
                decode_responses=False,  # We handle serialization manually
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
                max_connections=10
            )
            
            # Test connection
            await self._redis.ping()
            self._connected = True
            
            self.log_info(f"Connected to Redis",
                         cache=self.name,
                         redis_url=self.redis_url)
            
            return True
            
        except Exception as e:
            self._stats['connection_errors'] += 1
            self.log_error(f"Failed to connect to Redis",
                          cache=self.name,
                          redis_url=self.redis_url,
                          error=str(e))
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            try:
                await self._redis.close()
                self.log_info(f"Disconnected from Redis", cache=self.name)
            except Exception as e:
                self.log_error(f"Error disconnecting from Redis",
                              cache=self.name,
                              error=str(e))
            finally:
                self._redis = None
                self._connected = False
    
    async def _ensure_connected(self) -> bool:
        """Ensure Redis connection is active."""
        if not self._connected:
            return await self.connect()
        
        try:
            await self._redis.ping()
            return True
        except Exception:
            self._connected = False
            return await self.connect()
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        if self.serializer == "json":
            return json.dumps(value, default=str).encode('utf-8')
        elif self.serializer == "pickle":
            return pickle.dumps(value)
        else:
            raise ValueError(f"Unknown serializer: {self.serializer}")
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        if self.serializer == "json":
            return json.loads(data.decode('utf-8'))
        elif self.serializer == "pickle":
            return pickle.loads(data)
        else:
            raise ValueError(f"Unknown serializer: {self.serializer}")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        if not await self._ensure_connected():
            self._stats['errors'] += 1
            return None
        
        try:
            data = await self._redis.get(key)
            if data is None:
                self._stats['misses'] += 1
                self.log_debug(f"Cache miss for key: {key}",
                              cache=self.name,
                              key=key)
                return None
            
            value = self._deserialize(data)
            self._stats['hits'] += 1
            
            self.log_debug(f"Cache hit for key: {key}",
                          cache=self.name,
                          key=key)
            
            return value
            
        except Exception as e:
            self._stats['errors'] += 1
            self.log_error(f"Cache get error for key: {key}",
                          cache=self.name,
                          key=key,
                          error=str(e))
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis cache."""
        if not await self._ensure_connected():
            self._stats['errors'] += 1
            return False
        
        try:
            data = self._serialize(value)
            ttl_to_use = ttl or self.ttl
            
            await self._redis.setex(key, ttl_to_use, data)
            self._stats['sets'] += 1
            
            self.log_debug(f"Cache set for key: {key}",
                          cache=self.name,
                          key=key,
                          ttl=ttl_to_use,
                          size_bytes=len(data))
            
            return True
            
        except Exception as e:
            self._stats['errors'] += 1
            self.log_error(f"Cache set error for key: {key}",
                          cache=self.name,
                          key=key,
                          error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache."""
        if not await self._ensure_connected():
            self._stats['errors'] += 1
            return False
        
        try:
            result = await self._redis.delete(key)
            if result > 0:
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
        """Check if key exists in Redis cache."""
        if not await self._ensure_connected():
            return False
        
        try:
            result = await self._redis.exists(key)
            return result > 0
        except Exception as e:
            self.log_error(f"Cache exists error for key: {key}",
                          cache=self.name,
                          key=key,
                          error=str(e))
            return False
    
    async def clear(self) -> bool:
        """Clear all entries from Redis cache (use with caution)."""
        if not await self._ensure_connected():
            return False
        
        try:
            await self._redis.flushdb()
            self.log_warning(f"Cache cleared (FLUSHDB)",
                           cache=self.name)
            return True
            
        except Exception as e:
            self._stats['errors'] += 1
            self.log_error(f"Cache clear error",
                          cache=self.name,
                          error=str(e))
            return False
    
    async def keys(self, pattern: str = "*") -> list:
        """Get keys matching pattern."""
        if not await self._ensure_connected():
            return []
        
        try:
            keys = await self._redis.keys(pattern)
            return [key.decode('utf-8') if isinstance(key, bytes) else key for key in keys]
        except Exception as e:
            self.log_error(f"Cache keys error",
                          cache=self.name,
                          pattern=pattern,
                          error=str(e))
            return []
    
    async def size(self) -> int:
        """Get approximate cache size."""
        if not await self._ensure_connected():
            return 0
        
        try:
            info = await self._redis.info('keyspace')
            # Parse keyspace info for current database
            db_key = 'db0'  # Assuming default database
            if db_key in info:
                db_info = info[db_key]
                return db_info.get('keys', 0)
            return 0
        except Exception as e:
            self.log_error(f"Cache size error",
                          cache=self.name,
                          error=str(e))
            return 0
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            **self._stats,
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'connected': self._connected,
            'redis_url': self.redis_url,
            'ttl': self.ttl,
            'name': self.name,
            'serializer': self.serializer
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = {key: 0 for key in self._stats}
        self.log_info(f"Cache statistics reset", cache=self.name)


# Global L2 cache instance
_l2_cache: Optional[AsyncRedisCache] = None


def get_l2_cache() -> Optional[AsyncRedisCache]:
    """Get global L2 Redis cache instance."""
    global _l2_cache
    config = get_config()
    
    if not config.cache.l2_enabled or not REDIS_AVAILABLE:
        return None
    
    if _l2_cache is None:
        _l2_cache = AsyncRedisCache(
            redis_url=config.cache.l2_redis_url,
            ttl=config.cache.l2_ttl,
            name="GlobalL2Cache"
        )
    
    return _l2_cache


async def ensure_l2_connection():
    """Ensure L2 cache connection is established."""
    cache = get_l2_cache()
    if cache and REDIS_AVAILABLE:
        await cache.connect()