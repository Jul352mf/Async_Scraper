"""Tests for caching and concurrency utilities."""

import asyncio
import pytest

from scraper.core.cache.lru_cache import AsyncLRUCache, cached
from scraper.core.cache.cache_utils import get_cache_manager, cache_result
from scraper.core.cache.redis_cache import REDIS_AVAILABLE
from scraper.core.utils.concurrency import (
    SemaphorePool, BoundedQueue, CircuitBreaker, TaskGroup,
    gather_with_limit, CircuitBreakerOpenError
)


class TestAsyncLRUCache:
    """Test async LRU cache functionality."""
    
    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """Test basic cache operations."""
        cache = AsyncLRUCache(max_size=10, ttl=60, name="TestCache")
        
        # Test set and get
        await cache.set("key1", "value1")
        value = await cache.get("key1")
        assert value == "value1"
        
        # Test cache miss
        value = await cache.get("nonexistent")
        assert value is None
        
        # Test exists
        exists = await cache.exists("key1")
        assert exists is True
        
        exists = await cache.exists("nonexistent")
        assert exists is False
        
        # Test delete
        deleted = await cache.delete("key1")
        assert deleted is True
        
        value = await cache.get("key1")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics."""
        cache = AsyncLRUCache(max_size=10, ttl=60, name="StatsCache")
        
        # Generate some activity
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss
        
        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['sets'] == 1
        assert stats['hit_rate'] == 0.5
    
    @pytest.mark.asyncio
    async def test_cache_decorator(self):
        """Test cache decorator functionality."""
        call_count = 0
        
        @cached(ttl=60, key_prefix="test")
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call
        result1 = await expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call should hit cache
        result2 = await expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Should not increment
        
        # Different argument should miss cache
        result3 = await expensive_function(10)
        assert result3 == 20
        assert call_count == 2


class TestCacheManager:
    """Test cache manager functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_manager_operations(self):
        """Test cache manager basic operations."""
        manager = get_cache_manager()
        
        # Test set and get
        success = await manager.set("test_key", "test_value")
        assert success is True
        
        value = await manager.get("test_key")
        assert value == "test_value"
        
        # Test exists
        exists = await manager.exists("test_key")
        assert exists is True
        
        # Test delete
        deleted = await manager.delete("test_key")
        assert deleted is True
        
        value = await manager.get("test_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cache_result_decorator(self):
        """Test cache result decorator."""
        call_count = 0
        
        @cache_result(key_prefix="test_func", ttl=60)
        async def test_function(x: int) -> str:
            nonlocal call_count
            call_count += 1
            return f"result_{x}"
        
        # First call
        result1 = await test_function(42)
        assert result1 == "result_42"
        assert call_count == 1
        
        # Second call should hit cache
        result2 = await test_function(42)
        assert result2 == "result_42"
        assert call_count == 1
    
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
    @pytest.mark.asyncio
    async def test_cache_info(self):
        """Test cache info retrieval."""
        manager = get_cache_manager()
        
        # Set a test value
        await manager.set("info_test", "value")
        
        # Get cache info
        info = await manager.get_cache_info()
        
        assert 'enabled_layers' in info
        assert 'stats' in info
        assert 'layer_stats' in info


class TestSemaphorePool:
    """Test semaphore pool functionality."""
    
    @pytest.mark.asyncio
    async def test_semaphore_pool(self):
        """Test semaphore pool operations."""
        pool = SemaphorePool(max_concurrent=2, name="TestPool")
        
        results = []
        
        async def worker(worker_id: int):
            await pool.acquire()
            try:
                results.append(f"start_{worker_id}")
                await asyncio.sleep(0.1)  # Simulate work
                results.append(f"end_{worker_id}")
            finally:
                pool.release()
        
        # Start 3 workers with max_concurrent=2
        tasks = [
            asyncio.create_task(worker(1)),
            asyncio.create_task(worker(2)),
            asyncio.create_task(worker(3))
        ]
        
        await asyncio.gather(*tasks)
        
        # Check stats
        stats = pool.get_stats()
        assert stats['total_acquired'] == 3
        assert stats['total_released'] == 3
        assert stats['current_active'] == 0


class TestBoundedQueue:
    """Test bounded queue functionality."""
    
    @pytest.mark.asyncio
    async def test_bounded_queue(self):
        """Test bounded queue operations."""
        queue = BoundedQueue(maxsize=3, name="TestQueue")
        
        # Put items
        await queue.put("item1")
        await queue.put("item2")
        
        assert queue.qsize() == 2
        assert not queue.empty()
        assert not queue.full()
        
        # Get items
        item = await queue.get()
        assert item == "item1"
        
        item = await queue.get()
        assert item == "item2"
        
        assert queue.qsize() == 0
        assert queue.empty()
        
        # Check stats
        stats = queue.get_stats()
        assert stats['items_put'] == 2
        assert stats['items_got'] == 2


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self):
        """Test circuit breaker with successful calls."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1.0,
            name="TestBreaker"
        )
        
        async def successful_function():
            return "success"
        
        result = await breaker.call(successful_function)
        assert result == "success"
        
        stats = breaker.get_stats()
        assert stats['successful_calls'] == 1
        assert stats['current_state'] == 'closed'
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure(self):
        """Test circuit breaker with failures."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,
            name="FailureBreaker"
        )
        
        async def failing_function():
            raise ValueError("Test error")
        
        # First failure
        with pytest.raises(ValueError):
            await breaker.call(failing_function)
        
        assert breaker.state == 'closed'
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await breaker.call(failing_function)
        
        assert breaker.state == 'open'
        
        # Next call should fail immediately with circuit open
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_function)
        
        stats = breaker.get_stats()
        assert stats['failed_calls'] == 2
        assert stats['circuit_opens'] == 1


class TestTaskGroup:
    """Test task group functionality."""
    
    @pytest.mark.asyncio
    async def test_task_group(self):
        """Test task group operations."""
        group = TaskGroup(name="TestGroup")
        
        async def worker(worker_id: int, delay: float = 0.1):
            await asyncio.sleep(delay)
            return f"worker_{worker_id}"
        
        # Create tasks
        task1 = group.create_task(worker(1))
        task2 = group.create_task(worker(2))
        task3 = group.create_task(worker(3))
        
        # Wait for all tasks
        results = await group.wait_all(timeout=1.0)
        
        # Check results
        assert len(results) == 3
        assert "worker_1" in results
        assert "worker_2" in results
        assert "worker_3" in results
        
        # Check stats
        stats = group.get_stats()
        assert stats['tasks_created'] == 3
        assert stats['tasks_completed'] == 3
        assert stats['active_tasks'] == 0


class TestConcurrencyHelpers:
    """Test concurrency helper functions."""
    
    @pytest.mark.asyncio
    async def test_gather_with_limit(self):
        """Test gather with concurrency limit."""
        results = []
        
        async def worker(worker_id: int):
            results.append(f"start_{worker_id}")
            await asyncio.sleep(0.1)
            results.append(f"end_{worker_id}")
            return worker_id
        
        # Run 5 workers with limit of 2
        awaitables = [worker(i) for i in range(5)]
        values = await gather_with_limit(2, *awaitables)
        
        assert len(values) == 5
        assert set(values) == {0, 1, 2, 3, 4}
        assert len(results) == 10  # 5 starts + 5 ends


if __name__ == "__main__":
    pytest.main([__file__])