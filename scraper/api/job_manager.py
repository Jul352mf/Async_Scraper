"""
Job Manager

Manages job lifecycle, storage, and background processing.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Any, Callable
from uuid import uuid4
import structlog

from scraper.api.models import Job, JobStatus, JobType, JobProgress, DomainResult, EmailResult
from scraper.core.config import get_config
from scraper.core.logger import get_logger
from scraper.services.scraper_manager import ScraperManager

logger = get_logger(__name__)


class JobManager:
    """Manages job lifecycle and background processing."""
    
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.progress_callbacks: Dict[str, List[Callable]] = {}
        self.background_tasks: Dict[str, asyncio.Task] = {}
        self.config = get_config()
        
    def create_job(self, job_type: JobType, config: Dict[str, Any]) -> Job:
        """Create a new job."""
        job_id = str(uuid4())
        job = Job(
            id=job_id,
            type=job_type,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            config=config
        )
        
        self.jobs[job_id] = job
        self.progress_callbacks[job_id] = []
        
        logger.info("Created job", job_id=job_id, job_type=job_type)
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 100) -> List[Job]:
        """List jobs with optional status filter."""
        jobs = list(self.jobs.values())
        
        if status:
            jobs = [job for job in jobs if job.status == status]
            
        # Sort by creation time (newest first)
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        return jobs[:limit]
    
    def update_job_status(self, job_id: str, status: JobStatus, error_message: Optional[str] = None) -> bool:
        """Update job status."""
        if job_id not in self.jobs:
            return False
            
        job = self.jobs[job_id]
        old_status = job.status
        job.status = status
        
        if status == JobStatus.RUNNING and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            job.completed_at = datetime.now(timezone.utc)
            
        if error_message:
            job.error_message = error_message
            
        logger.info("Updated job status", job_id=job_id, old_status=old_status, new_status=status)
        
        # Notify progress callbacks
        self._notify_progress_callbacks(job_id)
        
        return True
    
    def update_job_progress(self, job_id: str, progress: JobProgress) -> bool:
        """Update job progress."""
        if job_id not in self.jobs:
            return False
            
        job = self.jobs[job_id]
        job.progress = progress
        
        # Estimate completion time
        if progress.completed > 0 and progress.total > progress.completed:
            elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
            rate = progress.completed / elapsed
            remaining = progress.total - progress.completed
            estimated_seconds = remaining / rate
            progress.estimated_completion = datetime.now(timezone.utc) + timedelta(seconds=estimated_seconds)
        
        logger.debug("Updated job progress", job_id=job_id, progress=progress.percent)
        
        # Notify progress callbacks
        self._notify_progress_callbacks(job_id)
        
        return True
    
    def add_progress_callback(self, job_id: str, callback: Callable):
        """Add progress callback for job."""
        if job_id in self.progress_callbacks:
            self.progress_callbacks[job_id].append(callback)
    
    def _notify_progress_callbacks(self, job_id: str):
        """Notify all progress callbacks for job."""
        if job_id in self.progress_callbacks:
            job = self.jobs[job_id]
            for callback in self.progress_callbacks[job_id]:
                try:
                    asyncio.create_task(callback(job))
                except Exception as e:
                    logger.error("Progress callback failed", job_id=job_id, error=str(e))
    
    async def start_job(self, job_id: str) -> bool:
        """Start job processing."""
        job = self.get_job(job_id)
        if not job or job.status != JobStatus.PENDING:
            return False
            
        # Update status to running
        self.update_job_status(job_id, JobStatus.RUNNING)
        
        # Start background processing
        if job.type == JobType.SCRAPE_COMPANIES:
            task = asyncio.create_task(self._process_companies_job(job_id))
        elif job.type == JobType.SCRAPE_DOMAINS:
            task = asyncio.create_task(self._process_domains_job(job_id))
        else:
            logger.error("Unknown job type", job_id=job_id, job_type=job.type)
            self.update_job_status(job_id, JobStatus.FAILED, "Unknown job type")
            return False
            
        self.background_tasks[job_id] = task
        
        logger.info("Started job processing", job_id=job_id)
        return True
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel job processing."""
        job = self.get_job(job_id)
        if not job:
            return False
            
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False
            
        # Cancel background task
        if job_id in self.background_tasks:
            task = self.background_tasks[job_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        self.update_job_status(job_id, JobStatus.CANCELLED)
        logger.info("Cancelled job", job_id=job_id)
        return True
    
    async def _process_companies_job(self, job_id: str):
        """Process companies scraping job."""
        job = self.get_job(job_id)
        if not job:
            return
            
        try:
            companies = job.config.get("companies", [])
            max_emails = job.config.get("max_emails_per_company", 10)
            
            # Initialize progress
            progress = JobProgress(
                total=len(companies),
                completed=0,
                percent=0.0
            )
            self.update_job_progress(job_id, progress)
            
            # Process each company
            results = []
            
            # Create scraper manager with job config
            manager = ScraperManager(self.config)
            
            # Update manager config with job-specific settings
            if "custom_config" in job.config and job.config["custom_config"]:
                # Apply custom config overrides
                custom_config = job.config["custom_config"]
                # This could update manager.config or pass additional parameters
                
            for i, company in enumerate(companies):
                if job.status == JobStatus.CANCELLED:
                    break
                    
                progress.current_item = company
                self.update_job_progress(job_id, progress)
                
                try:
                    # For companies, we need to convert to domains first
                    # This is simplified - in reality we'd need domain discovery
                    domain = f"{company.lower().replace(' ', '')}.com"
                    
                    # Process domain using existing scraper
                    logger.info("Processing company domain", company=company, domain=domain)
                    
                    # Add small delay to simulate processing
                    await asyncio.sleep(0.1)
                    
                    # This would integrate with the actual ScraperManager
                    # For now, create mock results
                    domain_result = DomainResult(
                        domain=domain,
                        emails=[],
                        status="completed",
                        processing_time=1.0
                    )
                    results.append(domain_result)
                    
                except Exception as e:
                    logger.error("Failed to process company", company=company, error=str(e))
                    domain_result = DomainResult(
                        domain=f"{company.lower().replace(' ', '')}.com",
                        emails=[],
                        status="failed", 
                        error=str(e),
                        processing_time=0.0
                    )
                    results.append(domain_result)
                    progress.failed += 1
                
                # Update progress
                progress.completed = i + 1
                progress.percent = (progress.completed / progress.total) * 100
                self.update_job_progress(job_id, progress)
            
            # Update final job status
            job.result_count = len([r for r in results if r.status == "completed"])
            
            if job.status == JobStatus.CANCELLED:
                logger.info("Job was cancelled", job_id=job_id)
            else:
                self.update_job_status(job_id, JobStatus.COMPLETED)
                logger.info("Job completed successfully", job_id=job_id, result_count=job.result_count)
                
        except Exception as e:
            logger.error("Job processing failed", job_id=job_id, error=str(e))
            self.update_job_status(job_id, JobStatus.FAILED, str(e))
        finally:
            # Cleanup
            if job_id in self.background_tasks:
                del self.background_tasks[job_id]
    
    async def _process_domains_job(self, job_id: str):
        """Process domains scraping job."""
        job = self.get_job(job_id)
        if not job:
            return
            
        try:
            domains = job.config.get("domains", [])
            max_emails = job.config.get("max_emails_per_domain", 10)
            crawl_depth = job.config.get("crawl_depth", 2)
            
            # Initialize progress
            progress = JobProgress(
                total=len(domains),
                completed=0,
                percent=0.0
            )
            self.update_job_progress(job_id, progress)
            
            # Process each domain
            results = []
            
            # Create scraper manager
            manager = ScraperManager(self.config)
            
            for i, domain in enumerate(domains):
                if job.status == JobStatus.CANCELLED:
                    break
                    
                progress.current_item = domain
                self.update_job_progress(job_id, progress)
                
                try:
                    # Process domain using existing scraper
                    logger.info("Processing domain", domain=domain)
                    
                    # Add small delay to simulate processing
                    await asyncio.sleep(0.1)
                    
                    # This is where we'd integrate with actual ScraperManager
                    # For now, create mock results
                    domain_result = DomainResult(
                        domain=domain,
                        emails=[],
                        status="completed",
                        processing_time=1.0
                    )
                    results.append(domain_result)
                    
                except Exception as e:
                    logger.error("Failed to process domain", domain=domain, error=str(e))
                    domain_result = DomainResult(
                        domain=domain,
                        emails=[],
                        status="failed",
                        error=str(e), 
                        processing_time=0.0
                    )
                    results.append(domain_result)
                    progress.failed += 1
                
                # Update progress
                progress.completed = i + 1
                progress.percent = (progress.completed / progress.total) * 100
                self.update_job_progress(job_id, progress)
            
            # Update final job status
            job.result_count = len([r for r in results if r.status == "completed"])
            
            if job.status == JobStatus.CANCELLED:
                logger.info("Job was cancelled", job_id=job_id)
            else:
                self.update_job_status(job_id, JobStatus.COMPLETED)
                logger.info("Job completed successfully", job_id=job_id, result_count=job.result_count)
                
        except Exception as e:
            logger.error("Job processing failed", job_id=job_id, error=str(e))
            self.update_job_status(job_id, JobStatus.FAILED, str(e))
        finally:
            # Cleanup
            if job_id in self.background_tasks:
                del self.background_tasks[job_id]
    
    def get_job_results(self, job_id: str) -> Optional[List[DomainResult]]:
        """Get job results (placeholder - would be stored separately)."""
        # In a real implementation, results would be stored in database
        # For now, return empty results
        return []
    
    def cleanup_old_jobs(self, max_age_days: int = 7):
        """Clean up old completed jobs."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        jobs_to_remove = []
        
        for job_id, job in self.jobs.items():
            if (job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED) and 
                job.completed_at and job.completed_at < cutoff_date):
                jobs_to_remove.append(job_id)
                
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
            if job_id in self.progress_callbacks:
                del self.progress_callbacks[job_id]
                
        if jobs_to_remove:
            logger.info("Cleaned up old jobs", count=len(jobs_to_remove))


# Global job manager instance
_job_manager = None

def get_job_manager() -> JobManager:
    """Get global job manager instance."""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager