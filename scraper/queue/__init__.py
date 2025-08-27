"""
Job queue system for background processing.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Any, Callable, Set, Union
from uuid import uuid4
from enum import Enum
import structlog

from scraper.core.logger import get_logger
from scraper.core.config import get_config

logger = get_logger(__name__)


class JobPriority(Enum):
    """Job priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class QueuedJob:
    """Represents a job in the queue."""
    
    def __init__(
        self,
        id: str,
        job_type: str,
        config: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        max_retries: int = 3,
        retry_delay: int = 60,
        depends_on: Optional[List[str]] = None,
    ):
        self.id = id
        self.job_type = job_type
        self.config = config
        self.priority = priority
        self.scheduled_at = scheduled_at or datetime.now(timezone.utc)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.depends_on = depends_on or []
        
        # Tracking
        self.created_at = datetime.now(timezone.utc)
        self.attempts = 0
        self.last_attempt_at: Optional[datetime] = None
        self.error_message: Optional[str] = None


class JobQueue:
    """Async job queue with priority and scheduling support."""
    
    def __init__(self, max_workers: int = 5, max_queue_size: int = 1000):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        
        # Job storage
        self._jobs: Dict[str, QueuedJob] = {}
        self._pending_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._processing: Dict[str, asyncio.Task] = {}
        self._completed: Set[str] = set()
        self._failed: Dict[str, str] = {}  # job_id -> error_message
        
        # Worker management
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._worker_semaphore = asyncio.Semaphore(max_workers)
        
        # Job handlers
        self._handlers: Dict[str, Callable] = {}
        
        # Event callbacks
        self._on_job_start: List[Callable] = []
        self._on_job_complete: List[Callable] = []
        self._on_job_failed: List[Callable] = []
        
        # Scheduler
        self._scheduler_task: Optional[asyncio.Task] = None
        
        self.config = get_config()
    
    def register_handler(self, job_type: str, handler: Callable) -> None:
        """Register a job handler for a specific job type."""
        self._handlers[job_type] = handler
        logger.info("Registered job handler", job_type=job_type)
    
    def on_job_start(self, callback: Callable) -> None:
        """Register callback for job start events."""
        self._on_job_start.append(callback)
    
    def on_job_complete(self, callback: Callable) -> None:
        """Register callback for job completion events."""
        self._on_job_complete.append(callback)
    
    def on_job_failed(self, callback: Callable) -> None:
        """Register callback for job failure events."""
        self._on_job_failed.append(callback)
    
    async def start(self) -> None:
        """Start the job queue workers."""
        if self._running:
            return
        
        self._running = True
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)
        
        # Start scheduler
        self._scheduler_task = asyncio.create_task(self._scheduler())
        
        logger.info("Job queue started", workers=self.max_workers)
    
    async def stop(self) -> None:
        """Stop the job queue workers."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel scheduler
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        # Cancel processing jobs
        for task in self._processing.values():
            task.cancel()
        
        self._workers.clear()
        self._processing.clear()
        
        logger.info("Job queue stopped")
    
    async def enqueue(self, job: QueuedJob) -> None:
        """Enqueue a job for processing."""
        if not self._running:
            raise RuntimeError("Job queue is not running")
        
        if job.id in self._jobs:
            raise ValueError(f"Job {job.id} already exists")
        
        # Check dependencies
        if job.depends_on:
            missing_deps = []
            for dep_id in job.depends_on:
                if dep_id not in self._completed and dep_id not in self._jobs:
                    missing_deps.append(dep_id)
            
            if missing_deps:
                raise ValueError(f"Missing dependencies: {missing_deps}")
        
        self._jobs[job.id] = job
        
        # If not scheduled for future, add to queue immediately
        if job.scheduled_at <= datetime.now(timezone.utc):
            await self._add_to_queue(job)
        
        logger.info("Job enqueued", job_id=job.id, job_type=job.job_type, priority=job.priority.name)
    
    async def _add_to_queue(self, job: QueuedJob) -> None:
        """Add job to processing queue."""
        # Check if dependencies are met
        if job.depends_on:
            unmet_deps = [dep for dep in job.depends_on if dep not in self._completed]
            if unmet_deps:
                logger.debug("Job dependencies not met", job_id=job.id, unmet_deps=unmet_deps)
                return
        
        # Priority queue uses negative priority for max-heap behavior
        priority_score = -job.priority.value
        await self._pending_queue.put((priority_score, job.id))
        logger.debug("Job added to processing queue", job_id=job.id)
    
    async def _worker(self, worker_name: str) -> None:
        """Worker coroutine that processes jobs."""
        logger.info("Worker started", worker=worker_name)
        
        while self._running:
            try:
                # Get job from queue with timeout
                try:
                    priority_score, job_id = await asyncio.wait_for(
                        self._pending_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                job = self._jobs.get(job_id)
                if not job:
                    logger.warning("Job not found", job_id=job_id, worker=worker_name)
                    continue
                
                # Process job
                await self._process_job(job, worker_name)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker error", worker=worker_name, error=str(e))
        
        logger.info("Worker stopped", worker=worker_name)
    
    async def _process_job(self, job: QueuedJob, worker_name: str) -> None:
        """Process a single job."""
        handler = self._handlers.get(job.job_type)
        if not handler:
            error_msg = f"No handler registered for job type: {job.job_type}"
            logger.error(error_msg, job_id=job.id)
            self._failed[job.id] = error_msg
            return
        
        async with self._worker_semaphore:
            job.attempts += 1
            job.last_attempt_at = datetime.now(timezone.utc)
            
            # Notify start callbacks
            for callback in self._on_job_start:
                try:
                    await callback(job)
                except Exception as e:
                    logger.error("Job start callback failed", error=str(e))
            
            logger.info("Processing job", job_id=job.id, job_type=job.job_type, 
                       attempt=job.attempts, worker=worker_name)
            
            try:
                # Execute job handler
                result = await handler(job.config)
                
                # Mark as completed
                self._completed.add(job.id)
                if job.id in self._processing:
                    del self._processing[job.id]
                
                # Notify completion callbacks
                for callback in self._on_job_complete:
                    try:
                        await callback(job, result)
                    except Exception as e:
                        logger.error("Job complete callback failed", error=str(e))
                
                logger.info("Job completed successfully", job_id=job.id, worker=worker_name)
                
                # Check for dependent jobs that can now run
                await self._check_dependent_jobs(job.id)
                
            except Exception as e:
                error_msg = str(e)
                job.error_message = error_msg
                
                # Check if we should retry
                if job.attempts < job.max_retries:
                    # Schedule retry
                    retry_at = datetime.now(timezone.utc) + timedelta(seconds=job.retry_delay)
                    job.scheduled_at = retry_at
                    
                    logger.warning("Job failed, will retry", job_id=job.id, 
                                 attempt=job.attempts, max_retries=job.max_retries,
                                 retry_at=retry_at, error=error_msg, worker=worker_name)
                else:
                    # Mark as permanently failed
                    self._failed[job.id] = error_msg
                    if job.id in self._processing:
                        del self._processing[job.id]
                    
                    # Notify failure callbacks
                    for callback in self._on_job_failed:
                        try:
                            await callback(job, error_msg)
                        except Exception as e:
                            logger.error("Job failed callback failed", error=str(e))
                    
                    logger.error("Job permanently failed", job_id=job.id, 
                               error=error_msg, worker=worker_name)
    
    async def _scheduler(self) -> None:
        """Scheduler coroutine that handles delayed jobs."""
        logger.info("Job scheduler started")
        
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                
                # Check for jobs ready to be scheduled
                for job_id, job in self._jobs.items():
                    if (job_id not in self._completed and 
                        job_id not in self._failed and 
                        job_id not in self._processing and
                        job.scheduled_at <= now):
                        
                        await self._add_to_queue(job)
                
                # Sleep before next check
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler error", error=str(e))
        
        logger.info("Job scheduler stopped")
    
    async def _check_dependent_jobs(self, completed_job_id: str) -> None:
        """Check for jobs that depend on the completed job."""
        for job_id, job in self._jobs.items():
            if (completed_job_id in job.depends_on and 
                job_id not in self._completed and 
                job_id not in self._failed):
                
                # Check if all dependencies are now met
                all_deps_met = all(dep in self._completed for dep in job.depends_on)
                if all_deps_met:
                    await self._add_to_queue(job)
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a job."""
        job = self._jobs.get(job_id)
        if not job:
            return {"status": "not_found"}
        
        if job_id in self._completed:
            status = "completed"
        elif job_id in self._failed:
            status = "failed"
            error = self._failed[job_id]
        elif job_id in self._processing:
            status = "processing"
        else:
            status = "pending"
        
        return {
            "status": status,
            "job_type": job.job_type,
            "priority": job.priority.name,
            "attempts": job.attempts,
            "max_retries": job.max_retries,
            "created_at": job.created_at.isoformat(),
            "scheduled_at": job.scheduled_at.isoformat(),
            "last_attempt_at": job.last_attempt_at.isoformat() if job.last_attempt_at else None,
            "error_message": job.error_message if job_id in self._failed else None,
        }
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "total_jobs": len(self._jobs),
            "pending": self._pending_queue.qsize(),
            "processing": len(self._processing),
            "completed": len(self._completed),
            "failed": len(self._failed),
            "workers": len(self._workers),
            "running": self._running,
        }


# Global job queue instance
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get the global job queue instance."""
    global _job_queue
    if _job_queue is None:
        config = get_config()
        _job_queue = JobQueue(
            max_workers=config.concurrency.max_concurrent_domains,
            max_queue_size=config.concurrency.max_queue_size,
        )
    return _job_queue


# Import Redis queue for production use
from .redis_queue import RedisJobQueue, create_redis_job_queue

__all__ = [
    "JobPriority",
    "QueuedJob", 
    "JobQueue",
    "get_job_queue",
    "RedisJobQueue",
    "create_redis_job_queue",
]