"""Concurrency utilities for managing async operations."""

import asyncio
import time
from typing import Any, Callable, List, Optional, Set

from scraper.core.config import get_config
from scraper.core.logger import get_logger, LoggerMixin

logger = get_logger(__name__)


class SemaphorePool(LoggerMixin):
    """Pool of semaphores for controlling concurrency."""
    
    def __init__(self, max_concurrent: int, name: str = "SemaphorePool"):
        """
        Initialize semaphore pool.
        
        Args:
            max_concurrent: Maximum concurrent operations
            name: Pool name for logging
        """
        super().__init__()
        self.max_concurrent = max_concurrent
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Statistics
        self._stats = {
            'total_acquired': 0,
            'total_released': 0,
            'current_active': 0,
            'max_active': 0,
            'total_wait_time': 0.0,
            'average_wait_time': 0.0
        }
        
        self.log_info(f"Initialized {self.name}",
                     max_concurrent=max_concurrent)
    
    async def acquire(self) -> None:
        """Acquire semaphore with timing."""
        start_time = time.time()
        
        await self.semaphore.acquire()
        
        wait_time = time.time() - start_time
        self._stats['total_acquired'] += 1
        self._stats['current_active'] += 1
        self._stats['total_wait_time'] += wait_time
        
        if self._stats['current_active'] > self._stats['max_active']:
            self._stats['max_active'] = self._stats['current_active']
        
        # Update average wait time
        if self._stats['total_acquired'] > 0:
            self._stats['average_wait_time'] = self._stats['total_wait_time'] / self._stats['total_acquired']
        
        if wait_time > 0.1:  # Log if wait time is significant
            self.log_debug(f"Semaphore acquired after wait",
                          pool=self.name,
                          wait_time=wait_time,
                          active=self._stats['current_active'])
    
    def release(self) -> None:
        """Release semaphore."""
        self.semaphore.release()
        self._stats['total_released'] += 1
        self._stats['current_active'] = max(0, self._stats['current_active'] - 1)
        
        self.log_debug(f"Semaphore released",
                      pool=self.name,
                      active=self._stats['current_active'])
    
    def get_stats(self) -> dict:
        """Get semaphore pool statistics."""
        return {
            **self._stats,
            'max_concurrent': self.max_concurrent,
            'available': self.semaphore._value,
            'utilization': (self.max_concurrent - self.semaphore._value) / self.max_concurrent
        }


class BoundedQueue(LoggerMixin):
    """Bounded queue with backpressure control."""
    
    def __init__(self, 
                 maxsize: int,
                 name: str = "BoundedQueue",
                 backpressure_threshold: float = 0.8):
        """
        Initialize bounded queue.
        
        Args:
            maxsize: Maximum queue size
            name: Queue name for logging
            backpressure_threshold: Threshold (0-1) when backpressure warnings start
        """
        super().__init__()
        self.maxsize = maxsize
        self.name = name
        self.backpressure_threshold = backpressure_threshold
        self.queue = asyncio.Queue(maxsize=maxsize)
        
        # Statistics
        self._stats = {
            'items_put': 0,
            'items_got': 0,
            'max_size_reached': 0,
            'backpressure_warnings': 0,
            'total_wait_time_put': 0.0,
            'total_wait_time_get': 0.0
        }
        
        self.log_info(f"Initialized {self.name}",
                     maxsize=maxsize,
                     backpressure_threshold=backpressure_threshold)
    
    async def put(self, item: Any) -> None:
        """Put item in queue with backpressure monitoring."""
        # Check backpressure
        current_size = self.queue.qsize()
        if current_size >= self.maxsize * self.backpressure_threshold:
            self._stats['backpressure_warnings'] += 1
            self.log_warning(f"Queue approaching capacity",
                           queue=self.name,
                           current_size=current_size,
                           max_size=self.maxsize,
                           utilization=current_size / self.maxsize)
        
        start_time = time.time()
        await self.queue.put(item)
        wait_time = time.time() - start_time
        
        self._stats['items_put'] += 1
        self._stats['total_wait_time_put'] += wait_time
        
        if current_size >= self.maxsize - 1:
            self._stats['max_size_reached'] += 1
    
    async def get(self) -> Any:
        """Get item from queue."""
        start_time = time.time()
        item = await self.queue.get()
        wait_time = time.time() - start_time
        
        self._stats['items_got'] += 1
        self._stats['total_wait_time_get'] += wait_time
        
        return item
    
    def put_nowait(self, item: Any) -> None:
        """Put item without waiting."""
        try:
            self.queue.put_nowait(item)
            self._stats['items_put'] += 1
        except asyncio.QueueFull:
            self._stats['max_size_reached'] += 1
            raise
    
    def get_nowait(self) -> Any:
        """Get item without waiting."""
        try:
            item = self.queue.get_nowait()
            self._stats['items_got'] += 1
            return item
        except asyncio.QueueEmpty:
            raise
    
    def task_done(self) -> None:
        """Mark task as done."""
        self.queue.task_done()
    
    async def join(self) -> None:
        """Wait for all tasks to complete."""
        await self.queue.join()
    
    def qsize(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self.queue.empty()
    
    def full(self) -> bool:
        """Check if queue is full."""
        return self.queue.full()
    
    def get_stats(self) -> dict:
        """Get queue statistics."""
        current_size = self.qsize()
        return {
            **self._stats,
            'current_size': current_size,
            'max_size': self.maxsize,
            'utilization': current_size / self.maxsize,
            'average_wait_put': (
                self._stats['total_wait_time_put'] / max(1, self._stats['items_put'])
            ),
            'average_wait_get': (
                self._stats['total_wait_time_get'] / max(1, self._stats['items_got'])
            )
        }


class CircuitBreaker(LoggerMixin):
    """Circuit breaker pattern for fault tolerance."""
    
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: type = Exception,
                 name: str = "CircuitBreaker"):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Timeout before attempting recovery
            expected_exception: Exception type that triggers circuit
            name: Circuit breaker name for logging
        """
        super().__init__()
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        # State management
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
        
        # Statistics
        self._stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'circuit_opens': 0,
            'circuit_closes': 0,
            'state_changes': []
        }
        
        self.log_info(f"Initialized {self.name}",
                     failure_threshold=failure_threshold,
                     recovery_timeout=recovery_timeout)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function through circuit breaker."""
        self._stats['total_calls'] += 1
        
        # Check circuit state
        if self.state == 'open':
            if self._should_attempt_reset():
                self._change_state('half-open')
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")
        
        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset failure count
            self._on_success()
            return result
            
        except self.expected_exception as e:
            # Failure - update state
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful call."""
        self._stats['successful_calls'] += 1
        
        if self.state == 'half-open':
            # Recovery successful
            self._change_state('closed')
            self.failure_count = 0
            self.log_info(f"Circuit breaker recovered",
                         circuit=self.name,
                         total_failures=self.failure_count)
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self._stats['failed_calls'] += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self._change_state('open')
            self.log_warning(f"Circuit breaker opened due to failures",
                           circuit=self.name,
                           failure_count=self.failure_count,
                           threshold=self.failure_threshold)
    
    def _change_state(self, new_state: str) -> None:
        """Change circuit breaker state."""
        old_state = self.state
        self.state = new_state
        
        # Update statistics
        if new_state == 'open':
            self._stats['circuit_opens'] += 1
        elif new_state == 'closed':
            self._stats['circuit_closes'] += 1
        
        self._stats['state_changes'].append({
            'from': old_state,
            'to': new_state,
            'timestamp': time.time(),
            'failure_count': self.failure_count
        })
        
        self.log_info(f"Circuit breaker state changed",
                     circuit=self.name,
                     from_state=old_state,
                     to_state=new_state)
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        success_rate = (
            self._stats['successful_calls'] / max(1, self._stats['total_calls'])
        )
        
        return {
            **self._stats,
            'current_state': self.state,
            'failure_count': self.failure_count,
            'success_rate': success_rate,
            'failure_threshold': self.failure_threshold,
            'recovery_timeout': self.recovery_timeout,
            'last_failure_time': self.last_failure_time
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class TaskGroup(LoggerMixin):
    """Structured concurrency task group (Python 3.11+ style)."""
    
    def __init__(self, name: str = "TaskGroup"):
        """Initialize task group."""
        super().__init__()
        self.name = name
        self.tasks: Set[asyncio.Task] = set()
        self._stats = {
            'tasks_created': 0,
            'tasks_completed': 0,
            'tasks_cancelled': 0,
            'tasks_failed': 0
        }
        
        self.log_debug(f"Initialized {self.name}")
    
    def create_task(self, coro) -> asyncio.Task:
        """Create and track a task."""
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        self._stats['tasks_created'] += 1
        
        # Add done callback to track completion
        task.add_done_callback(self._task_done_callback)
        
        self.log_debug(f"Created task",
                      group=self.name,
                      task_count=len(self.tasks))
        
        return task
    
    def _task_done_callback(self, task: asyncio.Task) -> None:
        """Callback when task completes."""
        self.tasks.discard(task)
        
        if task.cancelled():
            self._stats['tasks_cancelled'] += 1
        elif task.exception():
            self._stats['tasks_failed'] += 1
            self.log_error(f"Task failed",
                          group=self.name,
                          error=str(task.exception()))
        else:
            self._stats['tasks_completed'] += 1
    
    async def wait_all(self, timeout: Optional[float] = None) -> List[Any]:
        """Wait for all tasks to complete."""
        if not self.tasks:
            return []
        
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*self.tasks, return_exceptions=True),
                timeout=timeout
            )
            
            self.log_info(f"All tasks completed",
                         group=self.name,
                         task_count=len(self.tasks))
            
            return results
            
        except asyncio.TimeoutError:
            self.log_warning(f"Task group timeout",
                           group=self.name,
                           timeout=timeout)
            # Cancel remaining tasks
            await self.cancel_all()
            raise
    
    async def cancel_all(self) -> None:
        """Cancel all remaining tasks."""
        if not self.tasks:
            return
        
        self.log_info(f"Cancelling all tasks",
                     group=self.name,
                     task_count=len(self.tasks))
        
        for task in self.tasks:
            task.cancel()
        
        # Wait for cancellation to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
    
    def get_stats(self) -> dict:
        """Get task group statistics."""
        return {
            **self._stats,
            'active_tasks': len(self.tasks),
            'name': self.name
        }


# Convenience functions for common patterns
async def run_with_semaphore(semaphore: asyncio.Semaphore, 
                           func: Callable, 
                           *args, **kwargs) -> Any:
    """Run function with semaphore control."""
    async with semaphore:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)


async def gather_with_limit(limit: int, *awaitables, **kwargs) -> List[Any]:
    """Gather awaitables with concurrency limit."""
    semaphore = asyncio.Semaphore(limit)
    
    async def _limited_awaitable(awaitable):
        async with semaphore:
            return await awaitable
    
    limited_awaitables = [_limited_awaitable(aw) for aw in awaitables]
    return await asyncio.gather(*limited_awaitables, **kwargs)