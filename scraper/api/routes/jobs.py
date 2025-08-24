"""
Job Management API Routes

API endpoints for job status, results, and management.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import structlog

from scraper.api.models import Job, JobResponse, JobResult, JobStatus
from scraper.api.job_manager import get_job_manager, JobManager
from scraper.api.middleware.auth import get_current_api_key
from scraper.core.logger import get_logger

router = APIRouter(prefix="/api/v1", tags=["jobs"])
logger = get_logger(__name__)


@router.get("/jobs", response_model=List[Job])
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of jobs to return"),
    api_key: str = Depends(get_current_api_key),
    job_manager: JobManager = Depends(get_job_manager)
) -> List[Job]:
    """
    List all jobs with optional status filtering.
    
    Returns a list of jobs ordered by creation time (newest first).
    """
    
    logger.info("Listing jobs", status=status, limit=limit, api_key=api_key[:8] + "...")
    
    try:
        jobs = job_manager.list_jobs(status=status, limit=limit)
        
        logger.info("Listed jobs", count=len(jobs), status_filter=status)
        return jobs
        
    except Exception as e:
        logger.error("Failed to list jobs", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list jobs: {str(e)}"
        )


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    api_key: str = Depends(get_current_api_key),
    job_manager: JobManager = Depends(get_job_manager)
) -> Job:
    """
    Get detailed information about a specific job.
    
    Returns job details including status, progress, configuration, and metadata.
    """
    
    logger.info("Getting job details", job_id=job_id, api_key=api_key[:8] + "...")
    
    job = job_manager.get_job(job_id)
    if not job:
        logger.warning("Job not found", job_id=job_id)
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    logger.info("Retrieved job details", job_id=job_id, status=job.status)
    return job


@router.get("/jobs/{job_id}/results", response_model=JobResult)
async def get_job_results(
    job_id: str,
    api_key: str = Depends(get_current_api_key),
    job_manager: JobManager = Depends(get_job_manager)
) -> JobResult:
    """
    Get results for a completed job.
    
    Returns the extracted emails and processing results. Only available for completed jobs.
    """
    
    logger.info("Getting job results", job_id=job_id, api_key=api_key[:8] + "...")
    
    job = job_manager.get_job(job_id)
    if not job:
        logger.warning("Job not found", job_id=job_id)
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    if job.status != JobStatus.COMPLETED:
        logger.warning("Job not completed", job_id=job_id, status=job.status)
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not completed (status: {job.status})"
        )
    
    # Get results from job manager
    results = job_manager.get_job_results(job_id) or []
    
    # Create summary
    total_emails = sum(len(result.emails) if hasattr(result, 'emails') else 0 for result in results)
    successful_domains = len([r for r in results if hasattr(r, 'status') and r.status == "completed"])
    failed_domains = len([r for r in results if hasattr(r, 'status') and r.status == "failed"])
    
    summary = {
        "total_domains": len(results),
        "successful_domains": successful_domains,
        "failed_domains": failed_domains,
        "total_emails": total_emails,
        "processing_time": (job.completed_at - job.started_at).total_seconds() if job.completed_at and job.started_at else 0
    }
    
    job_result = JobResult(
        job_id=job_id,
        results=results,
        summary=summary,
        generated_at=job.completed_at or job.created_at
    )
    
    logger.info("Retrieved job results", job_id=job_id, total_emails=total_emails)
    return job_result


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    api_key: str = Depends(get_current_api_key),
    job_manager: JobManager = Depends(get_job_manager)
) -> JobResponse:
    """
    Cancel a running or pending job.
    
    Stops job processing and marks it as cancelled. Cannot cancel completed jobs.
    """
    
    logger.info("Cancelling job", job_id=job_id, api_key=api_key[:8] + "...")
    
    job = job_manager.get_job(job_id)
    if not job:
        logger.warning("Job not found", job_id=job_id)
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        logger.warning("Cannot cancel job", job_id=job_id, status=job.status)
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in status {job.status}"
        )
    
    # Cancel the job
    success = await job_manager.cancel_job(job_id)
    if not success:
        logger.error("Failed to cancel job", job_id=job_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel job {job_id}"
        )
    
    # Get updated job
    updated_job = job_manager.get_job(job_id)
    
    response = JobResponse(
        job=updated_job,
        message=f"Job {job_id} has been cancelled"
    )
    
    logger.info("Job cancelled successfully", job_id=job_id)
    return response


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    api_key: str = Depends(get_current_api_key),
    job_manager: JobManager = Depends(get_job_manager)
) -> JSONResponse:
    """
    Delete a job and all its data.
    
    Permanently removes job from the system. Can only delete completed, failed, or cancelled jobs.
    """
    
    logger.info("Deleting job", job_id=job_id, api_key=api_key[:8] + "...")
    
    job = job_manager.get_job(job_id)
    if not job:
        logger.warning("Job not found", job_id=job_id)
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
        logger.warning("Cannot delete active job", job_id=job_id, status=job.status)
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete job in status {job.status}. Cancel it first."
        )
    
    # Delete job (simplified - would need proper cleanup)
    if job_id in job_manager.jobs:
        del job_manager.jobs[job_id]
    if job_id in job_manager.progress_callbacks:
        del job_manager.progress_callbacks[job_id]
    
    logger.info("Job deleted successfully", job_id=job_id)
    
    return JSONResponse(
        status_code=200,
        content={"message": f"Job {job_id} has been deleted"}
    )