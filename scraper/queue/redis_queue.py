"""
Redis-based job queue implementation for production deployments.
"""

import asyncio
import json
import redis.asyncio as redis
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Any, Callable, Set, Union
from uuid import uuid4
from enum import Enum
import structlog

from scraper.core.logger import get_logger
from scraper.core.config import get_config
from scraper.queue import JobPriority, QueuedJob

logger = get_logger(__name__)


class RedisJobQueue:
    """Redis-based job queue with priority, scheduling, and reliability features."""
    
    def __init__(self, redis_url: str = None, max_workers: int = 5, key_prefix: str = "scraper:queue"):
        self.redis_url = redis_url or get_config().cache.l2_redis_url
        self.max_workers = max_workers
        self.key_prefix = key_prefix
        
        # Redis connection
        self.redis: Optional[redis.Redis] = None
        
        # Queue keys
        self.pending_key = f"{key_prefix}:pending"
        self.processing_key = f"{key_prefix}:processing"
        self.scheduled_key = f"{key_prefix}:scheduled"
        self.jobs_key = f"{key_prefix}:jobs"
        self.results_key = f"{key_prefix}:results"
        self.failed_key = f"{key_prefix}:failed"
        self.stats_key = f"{key_prefix}:stats"
        
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
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # Worker ID for distributed processing
        self.worker_id = f"worker-{uuid4().hex[:8]}"
        
        self.config = get_config()
    
    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self.redis:
            return
            
        try:
            self.redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                retry_on_error=[redis.BusyLoadingError, redis.ConnectionError],
            )
            
            # Test connection
            await self.redis.ping()
            
            logger.info(
                "Redis job queue initialized",
                redis_url=self.redis_url,
                worker_id=self.worker_id,
                key_prefix=self.key_prefix,
            )
            
        except Exception as e:
            logger.error("Failed to initialize Redis job queue", error=str(e))
            raise
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            self.redis = None
            logger.info("Redis connection closed")
    
    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        if not self.redis:
            return False
            
        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False
    
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
        
        await self.initialize()
        self._running = True
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"{self.worker_id}-{i}"))
            self._workers.append(worker)
        
        # Start scheduler
        self._scheduler_task = asyncio.create_task(self._scheduler())
        
        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        
        logger.info("Redis job queue started", workers=self.max_workers, worker_id=self.worker_id)
    
    async def stop(self) -> None:
        """Stop the job queue workers."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel scheduler and heartbeat
        for task in [self._scheduler_task, self._heartbeat_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers.clear()
        
        # Clean up processing jobs
        if self.redis:
            await self._cleanup_processing_jobs()
        
        await self.close()
        
        logger.info("Redis job queue stopped", worker_id=self.worker_id)
    
    async def enqueue(self, job: QueuedJob) -> None:
        """Enqueue a job for processing."""
        if not self._running:
            raise RuntimeError("Job queue is not running")
        
        if not self.redis:
            await self.initialize()
        
        # Check if job already exists
        job_exists = await self.redis.hexists(self.jobs_key, job.id)
        if job_exists:
            raise ValueError(f"Job {job.id} already exists")
        
        # Serialize job data
        job_data = {
            "id": job.id,
            "job_type": job.job_type,
            "config": json.dumps(job.config),
            "priority": job.priority.value,
            "scheduled_at": job.scheduled_at.isoformat(),
            "max_retries": job.max_retries,
            "retry_delay": job.retry_delay,
            "depends_on": json.dumps(job.depends_on),
            "created_at": job.created_at.isoformat(),
            "attempts": job.attempts,
        }
        
        # Store job data
        await self.redis.hset(self.jobs_key, job.id, json.dumps(job_data))
        
        # Add to appropriate queue
        now = datetime.now(timezone.utc)
        if job.scheduled_at <= now:
            # Check dependencies
            if job.depends_on:
                unmet_deps = await self._check_dependencies(job.depends_on)
                if unmet_deps:
                    # Add to scheduled queue with a small delay to check again
                    score = (now + timedelta(seconds=30)).timestamp()
                    await self.redis.zadd(self.scheduled_key, {job.id: score})
                    logger.debug("Job scheduled due to unmet dependencies", 
                               job_id=job.id, unmet_deps=unmet_deps)
                    return
            
            # Add to pending queue with priority score
            priority_score = -job.priority.value  # Higher priority = lower score
            await self.redis.zadd(self.pending_key, {job.id: priority_score})
        else:
            # Add to scheduled queue
            score = job.scheduled_at.timestamp()
            await self.redis.zadd(self.scheduled_key, {job.id: score})
        
        # Update stats
        await self.redis.hincrby(self.stats_key, "total_jobs", 1)
        
        logger.info("Job enqueued", job_id=job.id, job_type=job.job_type, 
                   priority=job.priority.name, worker_id=self.worker_id)
    
    async def _check_dependencies(self, depends_on: List[str]) -> List[str]:
        """Check which dependencies are not yet completed."""
        if not depends_on:
            return []
        
        # Check completed jobs (in results)
        completed_jobs = await self.redis.hmget(self.results_key, *depends_on)
        
        unmet_deps = []
        for i, dep_id in enumerate(depends_on):
            if completed_jobs[i] is None:  # Not in results
                # Check if job exists at all
                job_exists = await self.redis.hexists(self.jobs_key, dep_id)
                if not job_exists:
                    unmet_deps.append(dep_id)
        
        return unmet_deps
    
    async def _worker(self, worker_name: str) -> None:
        """Worker coroutine that processes jobs."""
        logger.info("Worker started", worker=worker_name)
        
        while self._running:
            try:
                # Get job from pending queue
                job_id = await self._get_next_job()
                if not job_id:
                    await asyncio.sleep(1.0)
                    continue
                
                # Process job
                await self._process_job(job_id, worker_name)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker error", worker=worker_name, error=str(e))
                await asyncio.sleep(1.0)
        
        logger.info("Worker stopped", worker=worker_name)
    
    async def _get_next_job(self) -> Optional[str]:
        """Get the next job from the pending queue."""
        if not self.redis:
            return None
        
        # Use ZPOPMIN to atomically get and remove the highest priority job
        result = await self.redis.zpopmin(self.pending_key)
        if not result:
            return None
        
        job_id, priority_score = result[0]
        
        # Move to processing set with worker info
        processing_data = {
            "worker": self.worker_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.redis.hset(self.processing_key, job_id, json.dumps(processing_data))
        
        return job_id
    
    async def _process_job(self, job_id: str, worker_name: str) -> None:
        """Process a single job."""
        if not self.redis:
            return
        
        # Get job data
        job_data_str = await self.redis.hget(self.jobs_key, job_id)
        if not job_data_str:
            logger.error("Job data not found", job_id=job_id)
            return
        
        try:
            job_data = json.loads(job_data_str)
            job_type = job_data["job_type"]
            config = json.loads(job_data["config"])
            
            handler = self._handlers.get(job_type)
            if not handler:
                error_msg = f"No handler registered for job type: {job_type}"
                logger.error(error_msg, job_id=job_id)
                await self._fail_job(job_id, error_msg)
                return
            
            async with self._worker_semaphore:
                # Update attempts
                attempts = job_data.get("attempts", 0) + 1
                job_data["attempts"] = attempts
                job_data["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
                await self.redis.hset(self.jobs_key, job_id, json.dumps(job_data))
                
                # Create QueuedJob object for callbacks
                queued_job = self._create_queued_job_from_data(job_data)
                
                # Notify start callbacks
                for callback in self._on_job_start:
                    try:
                        await callback(queued_job)
                    except Exception as e:
                        logger.error("Job start callback failed", error=str(e))
                
                logger.info("Processing job", job_id=job_id, job_type=job_type, 
                           attempt=attempts, worker=worker_name)
                
                try:
                    # Execute job handler
                    result = await handler(config)
                    
                    # Mark as completed
                    await self._complete_job(job_id, result)
                    
                    # Notify completion callbacks
                    for callback in self._on_job_complete:
                        try:
                            await callback(queued_job, result)
                        except Exception as e:
                            logger.error("Job complete callback failed", error=str(e))
                    
                    logger.info("Job completed successfully", job_id=job_id, worker=worker_name)
                    
                    # Check for dependent jobs
                    await self._check_dependent_jobs(job_id)
                    
                except Exception as e:
                    error_msg = str(e)
                    
                    # Check if we should retry
                    max_retries = job_data.get("max_retries", 3)
                    if attempts < max_retries:
                        # Schedule retry
                        retry_delay = job_data.get("retry_delay", 60)
                        retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
                        
                        job_data["scheduled_at"] = retry_at.isoformat()
                        job_data["error_message"] = error_msg
                        await self.redis.hset(self.jobs_key, job_id, json.dumps(job_data))
                        
                        # Remove from processing and add to scheduled
                        await self.redis.hdel(self.processing_key, job_id)
                        await self.redis.zadd(self.scheduled_key, {job_id: retry_at.timestamp()})
                        
                        logger.warning("Job failed, will retry", job_id=job_id, 
                                     attempt=attempts, max_retries=max_retries,
                                     retry_at=retry_at, error=error_msg, worker=worker_name)
                    else:
                        # Mark as permanently failed
                        await self._fail_job(job_id, error_msg)
                        
                        # Notify failure callbacks
                        for callback in self._on_job_failed:
                            try:
                                await callback(queued_job, error_msg)
                            except Exception as e:
                                logger.error("Job failed callback failed", error=str(e))
                        
                        logger.error("Job permanently failed", job_id=job_id, 
                                   error=error_msg, worker=worker_name)
        
        except Exception as e:
            logger.error("Error processing job", job_id=job_id, error=str(e))
            await self._fail_job(job_id, str(e))
    
    def _create_queued_job_from_data(self, job_data: Dict[str, Any]) -> QueuedJob:
        """Create QueuedJob object from Redis data."""
        return QueuedJob(
            id=job_data["id"],
            job_type=job_data["job_type"],
            config=json.loads(job_data["config"]),
            priority=JobPriority(job_data["priority"]),
            scheduled_at=datetime.fromisoformat(job_data["scheduled_at"]),
            max_retries=job_data["max_retries"],
            retry_delay=job_data["retry_delay"],
            depends_on=json.loads(job_data["depends_on"]),
        )
    
    async def _complete_job(self, job_id: str, result: Any) -> None:
        """Mark job as completed."""
        if not self.redis:
            return
        
        # Store result
        result_data = {
            "job_id": job_id,
            "result": json.dumps(result, default=str),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.redis.hset(self.results_key, job_id, json.dumps(result_data))
        
        # Remove from processing
        await self.redis.hdel(self.processing_key, job_id)
        
        # Update stats
        await self.redis.hincrby(self.stats_key, "completed_jobs", 1)
    
    async def _fail_job(self, job_id: str, error_message: str) -> None:
        """Mark job as permanently failed."""
        if not self.redis:
            return
        
        # Store failure info
        failure_data = {
            "job_id": job_id,
            "error_message": error_message,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.redis.hset(self.failed_key, job_id, json.dumps(failure_data))
        
        # Remove from processing
        await self.redis.hdel(self.processing_key, job_id)
        
        # Update stats
        await self.redis.hincrby(self.stats_key, "failed_jobs", 1)
    
    async def _scheduler(self) -> None:
        """Scheduler coroutine that handles delayed and dependency-blocked jobs."""
        logger.info("Redis job scheduler started", worker_id=self.worker_id)
        
        while self._running:
            try:
                if not self.redis:
                    await asyncio.sleep(5)
                    continue
                
                now = datetime.now(timezone.utc)
                now_timestamp = now.timestamp()
                
                # Get jobs ready to be scheduled
                ready_jobs = await self.redis.zrangebyscore(
                    self.scheduled_key, 0, now_timestamp, withscores=False, offset=0, num=100
                )
                
                for job_id in ready_jobs:
                    # Get job data to check dependencies
                    job_data_str = await self.redis.hget(self.jobs_key, job_id)
                    if not job_data_str:
                        # Job doesn't exist, remove from scheduled
                        await self.redis.zrem(self.scheduled_key, job_id)
                        continue
                    
                    try:
                        job_data = json.loads(job_data_str)
                        depends_on = json.loads(job_data.get("depends_on", "[]"))
                        
                        # Check dependencies
                        if depends_on:
                            unmet_deps = await self._check_dependencies(depends_on)
                            if unmet_deps:
                                # Dependencies still not met, reschedule for later
                                new_score = (now + timedelta(seconds=30)).timestamp()
                                await self.redis.zadd(self.scheduled_key, {job_id: new_score})
                                continue
                        
                        # Dependencies met or no dependencies, move to pending
                        priority = job_data.get("priority", JobPriority.NORMAL.value)
                        priority_score = -priority
                        
                        # Remove from scheduled, add to pending
                        await self.redis.zrem(self.scheduled_key, job_id)
                        await self.redis.zadd(self.pending_key, {job_id: priority_score})
                        
                        logger.debug("Job moved from scheduled to pending", job_id=job_id)
                        
                    except Exception as e:
                        logger.error("Error processing scheduled job", job_id=job_id, error=str(e))
                        # Remove problematic job from scheduled
                        await self.redis.zrem(self.scheduled_key, job_id)
                
                # Sleep before next check
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler error", error=str(e), worker_id=self.worker_id)
                await asyncio.sleep(5)
        
        logger.info("Redis job scheduler stopped", worker_id=self.worker_id)
    
    async def _heartbeat(self) -> None:
        """Heartbeat to track worker health and clean up stale jobs."""
        logger.info("Redis heartbeat started", worker_id=self.worker_id)
        
        while self._running:
            try:
                if not self.redis:
                    await asyncio.sleep(30)
                    continue
                
                # Update worker heartbeat
                heartbeat_data = {
                    "worker_id": self.worker_id,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "status": "alive",
                }
                await self.redis.hset(f"{self.key_prefix}:workers", 
                                    self.worker_id, json.dumps(heartbeat_data))
                
                # Clean up stale processing jobs (older than 10 minutes)
                await self._cleanup_stale_jobs()
                
                # Sleep for 30 seconds
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error", error=str(e), worker_id=self.worker_id)
                await asyncio.sleep(30)
        
        # Mark worker as stopped
        try:
            if self.redis:
                await self.redis.hdel(f"{self.key_prefix}:workers", self.worker_id)
        except:
            pass
        
        logger.info("Redis heartbeat stopped", worker_id=self.worker_id)
    
    async def _cleanup_stale_jobs(self) -> None:
        """Clean up jobs that have been processing for too long."""
        if not self.redis:
            return
        
        try:
            # Get all processing jobs
            processing_jobs = await self.redis.hgetall(self.processing_key)
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            
            for job_id, processing_data_str in processing_jobs.items():
                try:
                    processing_data = json.loads(processing_data_str)
                    started_at = datetime.fromisoformat(processing_data["started_at"])
                    
                    if started_at < cutoff_time:
                        # Job is stale, move back to pending
                        await self.redis.hdel(self.processing_key, job_id)
                        
                        # Get job data for priority
                        job_data_str = await self.redis.hget(self.jobs_key, job_id)
                        if job_data_str:
                            job_data = json.loads(job_data_str)
                            priority = job_data.get("priority", JobPriority.NORMAL.value)
                            priority_score = -priority
                            await self.redis.zadd(self.pending_key, {job_id: priority_score})
                            
                            logger.warning("Cleaned up stale job", job_id=job_id, 
                                         started_at=started_at)
                
                except Exception as e:
                    logger.error("Error cleaning up stale job", job_id=job_id, error=str(e))
        
        except Exception as e:
            logger.error("Error during stale job cleanup", error=str(e))
    
    async def _cleanup_processing_jobs(self) -> None:
        """Clean up processing jobs on shutdown."""
        if not self.redis:
            return
        
        try:
            # Get all jobs this worker was processing
            processing_jobs = await self.redis.hgetall(self.processing_key)
            
            for job_id, processing_data_str in processing_jobs.items():
                try:
                    processing_data = json.loads(processing_data_str)
                    if processing_data.get("worker") == self.worker_id:
                        # Move back to pending
                        await self.redis.hdel(self.processing_key, job_id)
                        
                        # Get job data for priority
                        job_data_str = await self.redis.hget(self.jobs_key, job_id)
                        if job_data_str:
                            job_data = json.loads(job_data_str)
                            priority = job_data.get("priority", JobPriority.NORMAL.value)
                            priority_score = -priority
                            await self.redis.zadd(self.pending_key, {job_id: priority_score})
                            
                            logger.info("Moved processing job back to pending", job_id=job_id)
                
                except Exception as e:
                    logger.error("Error moving processing job", job_id=job_id, error=str(e))
        
        except Exception as e:
            logger.error("Error during processing job cleanup", error=str(e))
    
    async def _check_dependent_jobs(self, completed_job_id: str) -> None:
        """Check for jobs that depend on the completed job."""
        if not self.redis:
            return
        
        try:
            # This is a simplified approach - in a more sophisticated system,
            # you might maintain a reverse dependency index
            
            # Get all scheduled jobs and check their dependencies
            scheduled_jobs = await self.redis.zrange(self.scheduled_key, 0, -1)
            
            for job_id in scheduled_jobs:
                job_data_str = await self.redis.hget(self.jobs_key, job_id)
                if not job_data_str:
                    continue
                
                try:
                    job_data = json.loads(job_data_str)
                    depends_on = json.loads(job_data.get("depends_on", "[]"))
                    
                    if completed_job_id in depends_on:
                        # Check if all dependencies are now met
                        unmet_deps = await self._check_dependencies(depends_on)
                        if not unmet_deps:
                            # All dependencies met, move to pending
                            priority = job_data.get("priority", JobPriority.NORMAL.value)
                            priority_score = -priority
                            
                            await self.redis.zrem(self.scheduled_key, job_id)
                            await self.redis.zadd(self.pending_key, {job_id: priority_score})
                            
                            logger.info("Dependent job ready for processing", 
                                      job_id=job_id, dependency=completed_job_id)
                
                except Exception as e:
                    logger.error("Error checking dependent job", job_id=job_id, error=str(e))
        
        except Exception as e:
            logger.error("Error checking dependent jobs", error=str(e))
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a job."""
        if not self.redis:
            await self.initialize()
        
        # Check if job exists
        job_data_str = await self.redis.hget(self.jobs_key, job_id)
        if not job_data_str:
            return {"status": "not_found"}
        
        try:
            job_data = json.loads(job_data_str)
            
            # Determine status
            if await self.redis.hexists(self.results_key, job_id):
                status = "completed"
                result_data_str = await self.redis.hget(self.results_key, job_id)
                result_data = json.loads(result_data_str) if result_data_str else {}
                completed_at = result_data.get("completed_at")
            elif await self.redis.hexists(self.failed_key, job_id):
                status = "failed"
                failure_data_str = await self.redis.hget(self.failed_key, job_id)
                failure_data = json.loads(failure_data_str) if failure_data_str else {}
                error_message = failure_data.get("error_message")
                completed_at = failure_data.get("failed_at")
            elif await self.redis.hexists(self.processing_key, job_id):
                status = "processing"
                completed_at = None
                error_message = None
            elif await self.redis.zscore(self.pending_key, job_id) is not None:
                status = "pending"
                completed_at = None
                error_message = None
            elif await self.redis.zscore(self.scheduled_key, job_id) is not None:
                status = "scheduled"
                completed_at = None
                error_message = None
            else:
                status = "unknown"
                completed_at = None
                error_message = None
            
            return {
                "status": status,
                "job_type": job_data["job_type"],
                "priority": job_data["priority"],
                "attempts": job_data["attempts"],
                "max_retries": job_data["max_retries"],
                "created_at": job_data["created_at"],
                "scheduled_at": job_data["scheduled_at"],
                "last_attempt_at": job_data.get("last_attempt_at"),
                "completed_at": completed_at,
                "error_message": error_message,
            }
            
        except Exception as e:
            logger.error("Error getting job status", job_id=job_id, error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self.redis:
            await self.initialize()
        
        try:
            # Get counts from Redis
            total_jobs = await self.redis.hlen(self.jobs_key)
            pending_jobs = await self.redis.zcard(self.pending_key)
            scheduled_jobs = await self.redis.zcard(self.scheduled_key)
            processing_jobs = await self.redis.hlen(self.processing_key)
            completed_jobs = await self.redis.hlen(self.results_key)
            failed_jobs = await self.redis.hlen(self.failed_key)
            
            # Get stats from stats key
            stats_data = await self.redis.hgetall(self.stats_key)
            
            # Get active workers
            active_workers = await self.redis.hlen(f"{self.key_prefix}:workers")
            
            return {
                "total_jobs": total_jobs,
                "pending": pending_jobs,
                "scheduled": scheduled_jobs,
                "processing": processing_jobs,
                "completed": completed_jobs,
                "failed": failed_jobs,
                "active_workers": active_workers,
                "current_worker": self.worker_id,
                "running": self._running,
                "redis_connected": await self.health_check(),
                "stats": stats_data,
            }
            
        except Exception as e:
            logger.error("Error getting queue stats", error=str(e))
            return {
                "error": str(e),
                "running": self._running,
                "redis_connected": False,
            }


# Factory function for creating Redis job queue
def create_redis_job_queue(redis_url: str = None, max_workers: int = 5) -> RedisJobQueue:
    """Create a Redis job queue instance."""
    return RedisJobQueue(redis_url=redis_url, max_workers=max_workers)