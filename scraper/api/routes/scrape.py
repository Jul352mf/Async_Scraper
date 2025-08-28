"""
Scraping API Routes

API endpoints for creating and managing scraping jobs.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog

from scraper.api.models import (
    ScrapeCompaniesRequest, ScrapeDomainsRequest, ScrapeResponse,
    Job, JobResponse, JobResult, JobStatus, JobType
)
from scraper.api.job_manager import get_job_manager, JobManager
from scraper.api.middleware.auth import get_current_api_key
from scraper.core.logger import get_logger

router = APIRouter(prefix="/api/v1", tags=["scraping"])
logger = get_logger(__name__)


@router.post("/scrape/companies", response_model=ScrapeResponse)
async def scrape_companies(
    request: ScrapeCompaniesRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_current_api_key),
    job_manager: JobManager = Depends(get_job_manager)
) -> ScrapeResponse:
    """
    Start a company email scraping job.
    
    This endpoint creates a background job to scrape emails from company websites.
    The job processes each company by discovering their domains and extracting emails.
    """
    
    logger.info(
        "Creating companies scraping job",
        company_count=len(request.companies),
        api_key=api_key[:8] + "..."
    )
    
    try:
        # Create job configuration
        job_config = {
            "companies": request.companies,
            "max_emails_per_company": request.max_emails_per_company,
            "include_subdomains": request.include_subdomains,
            "verify_emails": request.verify_emails,
            "timeout": request.timeout,
            "custom_config": request.custom_config
        }
        
        # Create job
        job = job_manager.create_job(JobType.SCRAPE_COMPANIES, job_config)
        
        # Start job in background
        background_tasks.add_task(job_manager.start_job, job.id)
        
        # Estimate duration (simplified calculation)
        estimated_minutes = len(request.companies) * 2  # 2 minutes per company
        estimated_duration = f"{estimated_minutes} minutes"
        
        response = ScrapeResponse(
            job_id=job.id,
            status=job.status.value,
            message=f"Created scraping job for {len(request.companies)} companies",
            estimated_duration=estimated_duration
        )
        
        logger.info(
            "Companies scraping job created",
            job_id=job.id,
            company_count=len(request.companies)
        )
        
        return response
        
    except Exception as e:
        logger.error("Failed to create companies scraping job", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create scraping job: {str(e)}"
        )


@router.post("/scrape/domains", response_model=ScrapeResponse)
async def scrape_domains(
    request: ScrapeDomainsRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_current_api_key),
    job_manager: JobManager = Depends(get_job_manager)
) -> ScrapeResponse:
    """
    Start a domain email scraping job.
    
    This endpoint creates a background job to scrape emails from specific domains.
    The job crawls each domain up to the specified depth and extracts email addresses.
    """
    
    logger.info(
        "Creating domains scraping job",
        domain_count=len(request.domains),
        crawl_depth=request.crawl_depth,
        api_key=api_key[:8] + "..."
    )
    
    try:
        # Create job configuration
        job_config = {
            "domains": request.domains,
            "max_emails_per_domain": request.max_emails_per_domain,
            "crawl_depth": request.crawl_depth,
            "verify_emails": request.verify_emails,
            "timeout": request.timeout,
            "custom_config": request.custom_config
        }
        
        # Create job
        job = job_manager.create_job(JobType.SCRAPE_DOMAINS, job_config)
        
        # Start job in background
        background_tasks.add_task(job_manager.start_job, job.id)
        
        # Estimate duration (simplified calculation)
        estimated_minutes = len(request.domains) * request.crawl_depth
        estimated_duration = f"{estimated_minutes} minutes"
        
        response = ScrapeResponse(
            job_id=job.id,
            status=job.status.value,
            message=f"Created scraping job for {len(request.domains)} domains",
            estimated_duration=estimated_duration
        )
        
        logger.info(
            "Domains scraping job created",
            job_id=job.id,
            domain_count=len(request.domains),
            crawl_depth=request.crawl_depth
        )
        
        return response
        
    except Exception as e:
        logger.error("Failed to create domains scraping job", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create scraping job: {str(e)}"
        )