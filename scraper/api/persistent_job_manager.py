"""
Persistent Job Manager with database integration and job queue support.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any, Callable, Union
from uuid import uuid4
import structlog

from scraper.api.models import Job, JobStatus, JobType, JobProgress, DomainResult, EmailResult
from scraper.core.config import get_config
from scraper.core.logger import get_logger
from scraper.services.scraper_manager import ScraperManager
from scraper.database import DatabaseManager, get_database_manager, JobModel, JobResultModel, run_migrations
from scraper.queue import JobQueue, QueuedJob, JobPriority, get_job_queue
from scraper.queue.redis_queue import RedisJobQueue, create_redis_job_queue

logger = get_logger(__name__)


class PersistentJobManager:
    """Manages job lifecycle with database persistence and queue processing."""
    
    def __init__(self):
        self.db = get_database_manager()
        self.config = get_config()
        
        # Choose queue backend based on configuration
        if self.config.queue.use_redis:
            self.queue = create_redis_job_queue(
                redis_url=self.config.queue.redis_url,
                max_workers=self.config.queue.max_workers
            )
            logger.info("Using Redis job queue backend")
        else:
            self.queue = get_job_queue()
            logger.info("Using in-memory job queue backend")
        
        self.progress_callbacks: Dict[str, List[Callable]] = {}
        self.scraper_manager = ScraperManager()
        
        # Register job handlers
        self._register_handlers()
        
        # Register queue callbacks
        self.queue.on_job_start(self._on_job_start)
        self.queue.on_job_complete(self._on_job_complete)
        self.queue.on_job_failed(self._on_job_failed)
    
    async def initialize(self) -> None:
        """Initialize the job manager."""
        # Initialize database and run migrations
        await self.db.initialize()
        
        if self.config.database.auto_migrate:
            await run_migrations(self.db)
        
        # Initialize job queue
        await self.queue.start()
        
        # Load pending jobs from database if using Redis (in-memory already handles this)
        if self.config.queue.use_redis:
            await self._load_pending_jobs()
        
        logger.info("Persistent job manager initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the job manager."""
        try:
            await self.queue.stop()
            await self.db.close()
            logger.info("Persistent job manager shutdown completed")


# Global persistent job manager instance
_persistent_job_manager: Optional[PersistentJobManager] = None


def get_persistent_job_manager() -> PersistentJobManager:
    """Get the global persistent job manager instance."""
    global _persistent_job_manager
    if _persistent_job_manager is None:
        _persistent_job_manager = PersistentJobManager()
    return _persistent_job_manager
        except Exception as e:
            logger.error("Error during job manager shutdown", error=str(e))
        await self.queue.stop()
        await self.db.close()
        logger.info("Persistent job manager shutdown")
    
    def _register_handlers(self) -> None:
        """Register job type handlers with the queue."""
        self.queue.register_handler("scrape_companies", self._handle_scrape_companies)
        self.queue.register_handler("scrape_companies_js", self._handle_scrape_companies_js)
        self.queue.register_handler("scrape_domains", self._handle_scrape_domains)
        self.queue.register_handler("scrape_domains_js", self._handle_scrape_domains_js)
    
    async def _load_pending_jobs(self) -> None:
        """Load pending jobs from database into queue."""
        try:
            # Get all pending/running jobs from database
            rows = await self.db.fetch("""
                SELECT * FROM jobs 
                WHERE status IN ('pending', 'running')
                ORDER BY created_at ASC
            """)
            
            for row in rows:
                job_model = JobModel.from_dict(row)
                
                # Create queued job
                queued_job = QueuedJob(
                    id=job_model.id,
                    job_type=job_model.type,
                    config=job_model.config,
                    priority=JobPriority.NORMAL,
                    scheduled_at=job_model.created_at,
                )
                
                # Enqueue the job
                await self.queue.enqueue(queued_job)
                
                logger.info("Loaded pending job from database", job_id=job_model.id)
            
            logger.info("Loaded pending jobs from database", count=len(rows))
            
        except Exception as e:
            logger.error("Failed to load pending jobs", error=str(e))
    
    async def create_job(self, job_type: JobType, config: Dict[str, Any]) -> Job:
        """Create a new job and persist to database."""
        job_id = str(uuid4())
        now = datetime.now(timezone.utc)
        
        # Insert job into database
        await self.db.execute("""
            INSERT INTO jobs (id, type, status, config, created_at, progress)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, job_id, job_type.value, JobStatus.PENDING.value, config, now, {})
        
        # Create queued job
        queued_job = QueuedJob(
            id=job_id,
            job_type=job_type.value,
            config=config,
            priority=JobPriority.NORMAL,
        )
        
        # Enqueue for processing
        await self.queue.enqueue(queued_job)
        
        self.progress_callbacks[job_id] = []
        
        job = Job(
            id=job_id,
            type=job_type,
            status=JobStatus.PENDING,
            created_at=now,
            config=config
        )
        
        logger.info("Created job", job_id=job_id, job_type=job_type.value)
        return job
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID from database."""
        row = await self.db.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if not row:
            return None
        
        job_model = JobModel.from_dict(row)
        return job_model.to_api_model()
    
    async def get_jobs(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[JobStatus] = None,
        job_type: Optional[JobType] = None
    ) -> List[Job]:
        """Get jobs with filtering and pagination."""
        conditions = []
        params = []
        param_count = 0
        
        if status:
            param_count += 1
            conditions.append(f"status = ${param_count}")
            params.append(status.value)
        
        if job_type:
            param_count += 1
            conditions.append(f"type = ${param_count}")
            params.append(job_type.value)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        param_count += 1
        params.append(limit)
        limit_clause = f"LIMIT ${param_count}"
        
        param_count += 1
        params.append(offset)
        offset_clause = f"OFFSET ${param_count}"
        
        query = f"""
            SELECT * FROM jobs 
            WHERE {where_clause}
            ORDER BY created_at DESC
            {limit_clause} {offset_clause}
        """
        
        rows = await self.db.fetch(query, *params)
        
        jobs = []
        for row in rows:
            job_model = JobModel.from_dict(row)
            jobs.append(job_model.to_api_model())
        
        return jobs
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        # Update database
        result = await self.db.execute("""
            UPDATE jobs 
            SET status = $1, updated_at = $2
            WHERE id = $3 AND status IN ('pending', 'running')
        """, JobStatus.CANCELLED.value, datetime.now(timezone.utc), job_id)
        
        if result == "UPDATE 0":
            return False
        
        logger.info("Job cancelled", job_id=job_id)
        return True
    
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job and its results."""
        # This will cascade delete job_results due to foreign key
        result = await self.db.execute("DELETE FROM jobs WHERE id = $1", job_id)
        
        if result == "DELETE 0":
            return False
        
        # Clean up callbacks
        if job_id in self.progress_callbacks:
            del self.progress_callbacks[job_id]
        
        logger.info("Job deleted", job_id=job_id)
        return True
    
    async def get_job_results(self, job_id: str) -> List[Any]:
        """Get results for a job."""
        rows = await self.db.fetch("""
            SELECT * FROM job_results 
            WHERE job_id = $1 
            ORDER BY created_at ASC
        """, job_id)
        
        results = []
        for row in rows:
            result_model = JobResultModel.from_dict(row)
            results.append(result_model.to_api_model())
        
        return results
    
    def add_progress_callback(self, job_id: str, callback: Callable) -> None:
        """Add progress callback for job updates."""
        if job_id not in self.progress_callbacks:
            self.progress_callbacks[job_id] = []
        self.progress_callbacks[job_id].append(callback)
    
    def remove_progress_callback(self, job_id: str, callback: Callable) -> None:
        """Remove progress callback."""
        if job_id in self.progress_callbacks:
            try:
                self.progress_callbacks[job_id].remove(callback)
            except ValueError:
                pass
    
    async def update_job_progress(self, job_id: str, progress: Dict[str, Any]) -> None:
        """Update job progress and notify callbacks."""
        # Update database
        await self.db.execute("""
            UPDATE jobs 
            SET progress = $1, updated_at = $2
            WHERE id = $3
        """, progress, datetime.now(timezone.utc), job_id)
        
        # Notify callbacks
        if job_id in self.progress_callbacks:
            for callback in self.progress_callbacks[job_id]:
                try:
                    await callback(job_id, progress)
                except Exception as e:
                    logger.error("Progress callback failed", job_id=job_id, error=str(e))
    
    async def _on_job_start(self, job: QueuedJob) -> None:
        """Handle job start event."""
        await self.db.execute("""
            UPDATE jobs 
            SET status = $1, started_at = $2, updated_at = $2
            WHERE id = $3
        """, JobStatus.RUNNING.value, datetime.now(timezone.utc), job.id)
        
        logger.info("Job started", job_id=job.id)
    
    async def _on_job_complete(self, job: QueuedJob, result: Any) -> None:
        """Handle job completion event."""
        now = datetime.now(timezone.utc)
        
        # Count results if they exist
        result_count = 0
        if isinstance(result, list):
            result_count = len(result)
        
        # Update job status
        await self.db.execute("""
            UPDATE jobs 
            SET status = $1, completed_at = $2, updated_at = $2, result_count = $3
            WHERE id = $4
        """, JobStatus.COMPLETED.value, now, now, result_count, job.id)
        
        # Store results if any
        if isinstance(result, list) and result:
            for item in result:
                result_id = str(uuid4())
                
                if isinstance(item, EmailResult):
                    result_type = "email"
                    data = item.model_dump()
                elif isinstance(item, DomainResult):
                    result_type = "domain"
                    data = item.model_dump()
                else:
                    result_type = "unknown"
                    data = {"data": item}
                
                await self.db.execute("""
                    INSERT INTO job_results (id, job_id, result_type, data, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                """, result_id, job.id, result_type, data, now)
        
        logger.info("Job completed", job_id=job.id, result_count=result_count)
    
    async def _on_job_failed(self, job: QueuedJob, error_message: str) -> None:
        """Handle job failure event."""
        await self.db.execute("""
            UPDATE jobs 
            SET status = $1, error_message = $2, updated_at = $3
            WHERE id = $4
        """, JobStatus.FAILED.value, error_message, datetime.now(timezone.utc), job.id)
        
        logger.error("Job failed", job_id=job.id, error=error_message)
    
    # Job handler methods
    async def _handle_scrape_companies(self, config: Dict[str, Any]) -> List[EmailResult]:
        """Handle company scraping job."""
        companies = config.get("companies", [])
        max_emails = config.get("max_emails_per_company", 10)
        
        results = []
        for company in companies:
            try:
                company_results = await self.scraper_manager.scrape_company_emails(
                    company, max_emails
                )
                results.extend(company_results)
            except Exception as e:
                logger.error("Company scraping failed", company=company, error=str(e))
        
        return results
    
    async def _handle_scrape_companies_js(self, config: Dict[str, Any]) -> List[EmailResult]:
        """Handle JavaScript-enabled company scraping job."""
        companies = config.get("companies", [])
        max_emails = config.get("max_emails_per_company", 10)
        js_config = config.get("config", {})
        
        results = []
        for company in companies:
            try:
                company_results = await self.scraper_manager.scrape_company_emails_js(
                    company, max_emails, js_config
                )
                results.extend(company_results)
            except Exception as e:
                logger.error("JS company scraping failed", company=company, error=str(e))
        
        return results
    
    async def _handle_scrape_domains(self, config: Dict[str, Any]) -> List[DomainResult]:
        """Handle domain scraping job."""
        domains = config.get("domains", [])
        max_emails = config.get("max_emails_per_domain", 50)
        
        results = []
        for domain in domains:
            try:
                domain_result = await self.scraper_manager.scrape_domain(
                    domain, max_emails
                )
                if domain_result:
                    results.append(domain_result)
            except Exception as e:
                logger.error("Domain scraping failed", domain=domain, error=str(e))
        
        return results
    
    async def _handle_scrape_domains_js(self, config: Dict[str, Any]) -> List[DomainResult]:
        """Handle JavaScript-enabled domain scraping job."""
        domains = config.get("domains", [])
        max_emails = config.get("max_emails_per_domain", 50)
        js_config = config.get("config", {})
        
        results = []
        for domain in domains:
            try:
                domain_result = await self.scraper_manager.scrape_domain_js(
                    domain, max_emails, js_config
                )
                if domain_result:
                    results.append(domain_result)
            except Exception as e:
                logger.error("JS domain scraping failed", domain=domain, error=str(e))
        
        return results


# Global persistent job manager instance
_persistent_job_manager: Optional[PersistentJobManager] = None


async def get_persistent_job_manager() -> PersistentJobManager:
    """Get the global persistent job manager instance."""
    global _persistent_job_manager
    if _persistent_job_manager is None:
        _persistent_job_manager = PersistentJobManager()
        await _persistent_job_manager.initialize()
    return _persistent_job_manager