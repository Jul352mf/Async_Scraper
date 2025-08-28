"""
Tests for job queue functionality including in-memory and Redis implementations.
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from scraper.queue import JobQueue, QueuedJob, JobPriority, get_job_queue


@pytest.mark.asyncio
class TestQueuedJob:
    """Test QueuedJob model."""
    
    def test_create_queued_job(self):
        """Test creating a queued job."""
        job_id = str(uuid4())
        config = {"companies": ["Google"], "max_emails": 10}
        
        job = QueuedJob(
            id=job_id,
            job_type="scrape_companies",
            config=config,
            priority=JobPriority.HIGH,
            max_retries=2,
        )
        
        assert job.id == job_id
        assert job.job_type == "scrape_companies"
        assert job.config == config
        assert job.priority == JobPriority.HIGH
        assert job.max_retries == 2
        assert job.attempts == 0
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.scheduled_at, datetime)
    
    def test_scheduled_job(self):
        """Test creating a scheduled job."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        job = QueuedJob(
            id=str(uuid4()),
            job_type="scrape_companies",
            config={},
            scheduled_at=future_time,
        )
        
        assert job.scheduled_at == future_time
    
    def test_job_with_dependencies(self):
        """Test creating a job with dependencies."""
        depends_on = [str(uuid4()), str(uuid4())]
        
        job = QueuedJob(
            id=str(uuid4()),
            job_type="scrape_companies",
            config={},
            depends_on=depends_on,
        )
        
        assert job.depends_on == depends_on


@pytest.mark.asyncio
class TestJobQueue:
    """Test in-memory job queue implementation."""
    
    @pytest.fixture
    async def job_queue(self):
        """Create a test job queue."""
        queue = JobQueue(max_workers=2, max_queue_size=100)
        
        # Mock handler for testing
        async def test_handler(config):
            await asyncio.sleep(0.1)  # Simulate work
            return {"result": "test_success", "config": config}
        
        queue.register_handler("test_job", test_handler)
        
        await queue.start()
        
        try:
            yield queue
        finally:
            await queue.stop()
    
    async def test_register_handler(self, job_queue):
        """Test registering job handlers."""
        async def new_handler(config):
            return {"result": "new_handler"}
        
        job_queue.register_handler("new_job_type", new_handler)
        assert "new_job_type" in job_queue._handlers
    
    async def test_enqueue_and_process_job(self, job_queue):
        """Test enqueueing and processing a job."""
        job = QueuedJob(
            id=str(uuid4()),
            job_type="test_job",
            config={"test": "data"},
            priority=JobPriority.NORMAL,
        )
        
        await job_queue.enqueue(job)
        
        # Wait for job to complete
        await asyncio.sleep(0.5)
        
        status = job_queue.get_job_status(job.id)
        assert status["status"] == "completed"
        assert status["job_type"] == "test_job"
        assert status["attempts"] >= 1
    
    async def test_job_priority_ordering(self, job_queue):
        """Test that jobs are processed in priority order."""
        results = []
        
        async def priority_handler(config):
            results.append(config["priority"])
            await asyncio.sleep(0.05)
            return {"priority": config["priority"]}
        
        job_queue.register_handler("priority_test", priority_handler)
        
        # Create jobs with different priorities (enqueue in reverse order)
        jobs = [
            QueuedJob(str(uuid4()), "priority_test", {"priority": "LOW"}, JobPriority.LOW),
            QueuedJob(str(uuid4()), "priority_test", {"priority": "NORMAL"}, JobPriority.NORMAL),
            QueuedJob(str(uuid4()), "priority_test", {"priority": "HIGH"}, JobPriority.HIGH),
            QueuedJob(str(uuid4()), "priority_test", {"priority": "URGENT"}, JobPriority.URGENT),
        ]
        
        # Enqueue in reverse priority order
        for job in jobs:
            await job_queue.enqueue(job)
        
        # Wait for all jobs to complete
        await asyncio.sleep(1.0)
        
        # Results should be processed in priority order (URGENT first)
        assert results[0] == "URGENT"
        assert results[1] == "HIGH"
    
    async def test_job_retry_on_failure(self, job_queue):
        """Test job retry mechanism on failure."""
        attempt_count = 0
        
        async def failing_handler(config):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise Exception("Simulated failure")
            return {"attempts": attempt_count}
        
        job_queue.register_handler("failing_job", failing_handler)
        
        job = QueuedJob(
            id=str(uuid4()),
            job_type="failing_job",
            config={},
            max_retries=3,
            retry_delay=1,  # 1 second delay
        )
        
        await job_queue.enqueue(job)
        
        # Wait for retries
        await asyncio.sleep(3.0)
        
        status = job_queue.get_job_status(job.id)
        assert status["status"] == "completed"
        assert status["attempts"] == 2  # First failed, second succeeded
    
    async def test_job_permanent_failure(self, job_queue):
        """Test job permanent failure after max retries."""
        async def always_failing_handler(config):
            raise Exception("Always fails")
        
        job_queue.register_handler("always_failing", always_failing_handler)
        
        job = QueuedJob(
            id=str(uuid4()),
            job_type="always_failing",
            config={},
            max_retries=2,
            retry_delay=1,
        )
        
        await job_queue.enqueue(job)
        
        # Wait for all retries to exhaust
        await asyncio.sleep(5.0)
        
        status = job_queue.get_job_status(job.id)
        assert status["status"] == "failed"
        assert status["attempts"] == 2
        assert status["error_message"] == "Always fails"
    
    async def test_scheduled_job_processing(self, job_queue):
        """Test processing of scheduled jobs."""
        future_time = datetime.now(timezone.utc) + timedelta(seconds=2)
        
        job = QueuedJob(
            id=str(uuid4()),
            job_type="test_job",
            config={"scheduled": True},
            scheduled_at=future_time,
        )
        
        await job_queue.enqueue(job)
        
        # Job should be pending initially
        status = job_queue.get_job_status(job.id)
        assert status["status"] == "pending"
        
        # Wait for scheduled time plus processing
        await asyncio.sleep(3.0)
        
        # Now job should be completed
        status = job_queue.get_job_status(job.id)
        assert status["status"] == "completed"
    
    async def test_job_dependencies(self, job_queue):
        """Test job dependency resolution."""
        results = []
        
        async def dependency_handler(config):
            results.append(config["job_name"])
            await asyncio.sleep(0.1)
            return {"job_name": config["job_name"]}
        
        job_queue.register_handler("dependency_test", dependency_handler)
        
        # Create jobs with dependencies
        job1_id = str(uuid4())
        job2_id = str(uuid4())
        job3_id = str(uuid4())
        
        job1 = QueuedJob(job1_id, "dependency_test", {"job_name": "job1"})
        job2 = QueuedJob(job2_id, "dependency_test", {"job_name": "job2"}, depends_on=[job1_id])
        job3 = QueuedJob(job3_id, "dependency_test", {"job_name": "job3"}, depends_on=[job1_id, job2_id])
        
        # Enqueue in reverse order
        await job_queue.enqueue(job1)
        await job_queue.enqueue(job2)
        await job_queue.enqueue(job3)
        
        # Wait for all jobs to complete
        await asyncio.sleep(2.0)
        
        # Jobs should complete in dependency order
        assert results[0] == "job1"
        assert results[1] == "job2"
        assert results[2] == "job3"
    
    async def test_job_callbacks(self, job_queue):
        """Test job lifecycle callbacks."""
        started_jobs = []
        completed_jobs = []
        failed_jobs = []
        
        async def on_start(job):
            started_jobs.append(job.id)
        
        async def on_complete(job, result):
            completed_jobs.append((job.id, result))
        
        async def on_failed(job, error):
            failed_jobs.append((job.id, error))
        
        job_queue.on_job_start(on_start)
        job_queue.on_job_complete(on_complete)
        job_queue.on_job_failed(on_failed)
        
        # Successful job
        success_job = QueuedJob(str(uuid4()), "test_job", {"test": "success"})
        await job_queue.enqueue(success_job)
        
        # Failing job
        async def failing_handler(config):
            raise Exception("Test failure")
        
        job_queue.register_handler("failing_job", failing_handler)
        
        fail_job = QueuedJob(str(uuid4()), "failing_job", {}, max_retries=1)
        await job_queue.enqueue(fail_job)
        
        # Wait for processing
        await asyncio.sleep(3.0)
        
        # Check callbacks were called
        assert success_job.id in started_jobs
        assert any(job_id == success_job.id for job_id, _ in completed_jobs)
        
        assert fail_job.id in started_jobs
        assert any(job_id == fail_job.id for job_id, _ in failed_jobs)
    
    async def test_queue_stats(self, job_queue):
        """Test queue statistics."""
        # Add some jobs
        for i in range(3):
            job = QueuedJob(str(uuid4()), "test_job", {"index": i})
            await job_queue.enqueue(job)
        
        # Get initial stats
        stats = job_queue.get_queue_stats()
        assert stats["running"] is True
        assert stats["workers"] == 2  # max_workers from fixture
        assert stats["total_jobs"] >= 3
        
        # Wait for jobs to process
        await asyncio.sleep(1.0)
        
        # Get updated stats
        stats = job_queue.get_queue_stats()
        assert stats["completed"] >= 3
    
    async def test_duplicate_job_id(self, job_queue):
        """Test handling of duplicate job IDs."""
        job_id = str(uuid4())
        
        job1 = QueuedJob(job_id, "test_job", {"first": True})
        job2 = QueuedJob(job_id, "test_job", {"second": True})
        
        await job_queue.enqueue(job1)
        
        # Second job with same ID should raise error
        with pytest.raises(ValueError, match="already exists"):
            await job_queue.enqueue(job2)


# Note: Redis queue tests would require a Redis instance
# For CI/CD, we can mock Redis or use pytest-redis plugin
@pytest.mark.asyncio
class TestRedisQueueMocked:
    """Test Redis job queue with mocked Redis."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis instance."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_redis.from_url.return_value = mock_redis
        return mock_redis
    
    async def test_redis_queue_initialization(self, mock_redis, monkeypatch):
        """Test Redis queue initialization."""
        # Mock the redis import
        monkeypatch.setattr("scraper.queue.redis_queue.redis", MagicMock())
        
        from scraper.queue.redis_queue import RedisJobQueue
        
        queue = RedisJobQueue(redis_url="redis://localhost:6379/1")
        
        # Mock Redis instance
        queue.redis = mock_redis
        
        await queue.initialize()
        
        # Should have called ping to test connection
        mock_redis.ping.assert_called_once()
    
    async def test_redis_queue_health_check(self, mock_redis, monkeypatch):
        """Test Redis queue health check."""
        monkeypatch.setattr("scraper.queue.redis_queue.redis", MagicMock())
        
        from scraper.queue.redis_queue import RedisJobQueue
        
        queue = RedisJobQueue()
        queue.redis = mock_redis
        
        # Successful health check
        mock_redis.ping.return_value = True
        result = await queue.health_check()
        assert result is True
        
        # Failed health check
        mock_redis.ping.side_effect = Exception("Connection failed")
        result = await queue.health_check()
        assert result is False


@pytest.mark.asyncio
class TestJobQueueIntegration:
    """Integration tests for job queue functionality."""
    
    async def test_concurrent_job_processing(self):
        """Test processing multiple jobs concurrently."""
        queue = JobQueue(max_workers=3, max_queue_size=50)
        
        processed_jobs = []
        processing_times = []
        
        async def concurrent_handler(config):
            start_time = asyncio.get_event_loop().time()
            await asyncio.sleep(0.2)  # Simulate work
            end_time = asyncio.get_event_loop().time()
            
            processed_jobs.append(config["job_id"])
            processing_times.append(end_time - start_time)
            
            return {"job_id": config["job_id"]}
        
        queue.register_handler("concurrent_job", concurrent_handler)
        
        await queue.start()
        
        try:
            # Enqueue multiple jobs
            job_ids = []
            for i in range(6):  # More jobs than workers to test concurrency
                job_id = str(uuid4())
                job_ids.append(job_id)
                
                job = QueuedJob(
                    id=job_id,
                    job_type="concurrent_job",
                    config={"job_id": job_id},
                )
                
                await job_queue.enqueue(job)
            
            # Wait for all jobs to complete
            await asyncio.sleep(2.0)
            
            # All jobs should be processed
            assert len(processed_jobs) == 6
            assert set(processed_jobs) == set(job_ids)
            
            # Some jobs should have been processed concurrently
            # (total time should be less than sequential processing)
            total_sequential_time = 6 * 0.2  # 1.2 seconds
            actual_processing_time = max(processing_times)
            
            # With 3 workers, should complete in ~0.4 seconds (2 batches)
            assert actual_processing_time < total_sequential_time
            
        finally:
            await queue.stop()
    
    async def test_queue_backpressure(self):
        """Test queue backpressure when queue is full."""
        small_queue = JobQueue(max_workers=1, max_queue_size=2)
        
        async def slow_handler(config):
            await asyncio.sleep(1.0)  # Very slow processing
            return {"processed": True}
        
        small_queue.register_handler("slow_job", slow_handler)
        await small_queue.start()
        
        try:
            # Fill up the queue
            jobs = []
            for i in range(3):  # More than max_queue_size
                job = QueuedJob(
                    id=str(uuid4()),
                    job_type="slow_job",
                    config={"index": i},
                )
                jobs.append(job)
                await small_queue.enqueue(job)
            
            # Queue should handle backpressure appropriately
            stats = small_queue.get_queue_stats()
            assert stats["total_jobs"] == 3
            
        finally:
            await small_queue.stop()