"""
Enhanced scraping API endpoints with JavaScript support.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import structlog

from scraper.api.middleware.auth import get_current_api_key
from scraper.api.job_manager import get_job_manager
from scraper.api.models.scrape import (
    CompanyScrapingRequest, 
    DomainScrapingRequest,
    ScrapingJobResponse
)
from scraper.api.models.jobs import JobType
from scraper.services.js_scraper import JavaScriptScraper
from scraper.services.capture import get_capture_service
from scraper.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/enhanced", tags=["enhanced-scraping"])


@router.post("/scrape/companies/js", response_model=ScrapingJobResponse)
async def scrape_companies_with_javascript(
    request: CompanyScrapingRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_current_api_key)
) -> ScrapingJobResponse:
    """
    Create a job to scrape companies using JavaScript-enabled browser automation.
    
    This endpoint uses Playwright to render JavaScript content and extract emails
    from dynamically loaded content that traditional scraping might miss.
    """
    try:
        job_manager = get_job_manager()
        
        # Create job configuration
        job_config = {
            "companies": request.companies,
            "max_emails_per_company": request.max_emails_per_company,
            "use_javascript": True,
            "take_screenshots": request.config.get("take_screenshots", False) if request.config else False,
            "browser_type": request.config.get("browser_type", "chromium") if request.config else "chromium"
        }
        
        # Override with custom config if provided
        if request.config:
            job_config.update(request.config)
        
        # Create the job
        job = job_manager.create_job(JobType.SCRAPE_COMPANIES, job_config)
        
        # Start background processing
        background_tasks.add_task(
            _process_companies_with_js,
            job.id,
            job_config
        )
        
        logger.info("JavaScript companies scraping job created",
                   job_id=str(job.id),
                   companies=len(request.companies),
                   api_key=api_key)
        
        return ScrapingJobResponse(
            job_id=str(job.id),
            status=job.status,
            message=f"Created JavaScript scraping job for {len(request.companies)} companies",
            estimated_completion=job.estimated_completion
        )
        
    except Exception as e:
        logger.error("Failed to create JavaScript companies scraping job", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create scraping job")


@router.post("/scrape/domains/js", response_model=ScrapingJobResponse)
async def scrape_domains_with_javascript(
    request: DomainScrapingRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_current_api_key)
) -> ScrapingJobResponse:
    """
    Create a job to scrape domains using JavaScript-enabled browser automation.
    
    This endpoint crawls domains with JavaScript rendering to extract emails
    from single-page applications and dynamically loaded content.
    """
    try:
        job_manager = get_job_manager()
        
        # Create job configuration
        job_config = {
            "domains": request.domains,
            "max_depth": request.max_depth,
            "max_emails_per_domain": request.max_emails_per_domain,
            "use_javascript": True,
            "take_screenshots": request.config.get("take_screenshots", False) if request.config else False,
            "browser_type": request.config.get("browser_type", "chromium") if request.config else "chromium"
        }
        
        # Override with custom config if provided
        if request.config:
            job_config.update(request.config)
        
        # Create the job
        job = job_manager.create_job(JobType.SCRAPE_DOMAINS, job_config)
        
        # Start background processing
        background_tasks.add_task(
            _process_domains_with_js,
            job.id,
            job_config
        )
        
        logger.info("JavaScript domains scraping job created",
                   job_id=str(job.id),
                   domains=len(request.domains),
                   api_key=api_key)
        
        return ScrapingJobResponse(
            job_id=str(job.id),
            status=job.status,
            message=f"Created JavaScript scraping job for {len(request.domains)} domains",
            estimated_completion=job.estimated_completion
        )
        
    except Exception as e:
        logger.error("Failed to create JavaScript domains scraping job", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create scraping job")


async def _process_companies_with_js(job_id: str, config: Dict[str, Any]) -> None:
    """Process companies scraping job with JavaScript support."""
    job_manager = get_job_manager()
    js_scraper = JavaScriptScraper()
    
    try:
        job_manager.update_job_status(job_id, "running")
        
        companies = config["companies"]
        max_emails = config.get("max_emails_per_company", 50)
        take_screenshots = config.get("take_screenshots", False)
        
        results = {}
        total_emails = 0
        
        for i, company in enumerate(companies):
            try:
                # Update progress
                progress = {
                    "percent": (i / len(companies)) * 100,
                    "current_item": company,
                    "total_items": len(companies),
                    "completed_items": i
                }
                job_manager.update_job_progress(job_id, progress)
                
                # Scrape company with JavaScript
                result = await js_scraper.scrape_company_with_js(
                    company_name=company,
                    max_emails=max_emails
                )
                
                if result.success:
                    results[company] = result.emails
                    total_emails += len(result.emails)
                else:
                    results[company] = []
                    logger.warning("Company scraping failed",
                                 company=company,
                                 error=result.error)
                
            except Exception as e:
                logger.error("Error processing company", company=company, error=str(e))
                results[company] = []
        
        # Final progress update
        final_progress = {
            "percent": 100.0,
            "current_item": "Completed",
            "total_items": len(companies),
            "completed_items": len(companies)
        }
        job_manager.update_job_progress(job_id, final_progress)
        
        # Store results
        job_results = {
            "companies_processed": len(companies),
            "total_emails_found": total_emails,
            "emails_by_company": results,
            "processing_method": "javascript"
        }
        
        job_manager.complete_job(job_id, job_results)
        logger.info("JavaScript companies scraping completed",
                   job_id=job_id,
                   total_emails=total_emails)
        
    except Exception as e:
        logger.error("JavaScript companies scraping failed", job_id=job_id, error=str(e))
        job_manager.fail_job(job_id, str(e))


async def _process_domains_with_js(job_id: str, config: Dict[str, Any]) -> None:
    """Process domains scraping job with JavaScript support."""
    job_manager = get_job_manager()
    js_scraper = JavaScriptScraper()
    
    try:
        job_manager.update_job_status(job_id, "running")
        
        domains = config["domains"]
        max_depth = config.get("max_depth", 3)
        max_emails = config.get("max_emails_per_domain", 100)
        
        results = {}
        total_emails = 0
        
        for i, domain in enumerate(domains):
            try:
                # Update progress
                progress = {
                    "percent": (i / len(domains)) * 100,
                    "current_item": domain,
                    "total_items": len(domains),
                    "completed_items": i
                }
                job_manager.update_job_progress(job_id, progress)
                
                # Scrape domain with JavaScript
                domain_results = await js_scraper.scrape_domain(
                    domain=domain,
                    max_pages=min(20, max_emails // 5),
                    max_depth=max_depth
                )
                
                # Collect all emails from domain
                domain_emails = []
                for result in domain_results:
                    if result.success:
                        domain_emails.extend(result.emails)
                
                # Remove duplicates and limit
                unique_emails = list(set(domain_emails))[:max_emails]
                results[domain] = unique_emails
                total_emails += len(unique_emails)
                
            except Exception as e:
                logger.error("Error processing domain", domain=domain, error=str(e))
                results[domain] = []
        
        # Final progress update
        final_progress = {
            "percent": 100.0,
            "current_item": "Completed",
            "total_items": len(domains),
            "completed_items": len(domains)
        }
        job_manager.update_job_progress(job_id, final_progress)
        
        # Store results
        job_results = {
            "domains_processed": len(domains),
            "total_emails_found": total_emails,
            "emails_by_domain": results,
            "processing_method": "javascript"
        }
        
        job_manager.complete_job(job_id, job_results)
        logger.info("JavaScript domains scraping completed",
                   job_id=job_id,
                   total_emails=total_emails)
        
    except Exception as e:
        logger.error("JavaScript domains scraping failed", job_id=job_id, error=str(e))
        job_manager.fail_job(job_id, str(e))


# Capture service endpoints
@router.post("/capture/screenshot")
async def capture_screenshot(
    url: str,
    full_page: bool = True,
    api_key: str = Depends(get_current_api_key)
) -> Dict[str, Any]:
    """
    Take a screenshot of a webpage using browser automation.
    """
    try:
        capture_service = get_capture_service()
        
        result = await capture_service.take_screenshot(
            url=url,
            full_page=full_page
        )
        
        if result.success:
            logger.info("Screenshot captured", url=url, api_key=api_key)
            return {
                "success": True,
                "file_path": result.file_path,
                "file_size": result.file_size,
                "processing_time": result.processing_time
            }
        else:
            logger.warning("Screenshot failed", url=url, error=result.error)
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error("Screenshot capture failed", url=url, error=str(e))
        raise HTTPException(status_code=500, detail="Screenshot capture failed")


@router.post("/capture/pdf")
async def capture_pdf(
    url: str,
    format: str = "A4",
    landscape: bool = False,
    api_key: str = Depends(get_current_api_key)
) -> Dict[str, Any]:
    """
    Generate a PDF of a webpage using browser automation.
    """
    try:
        capture_service = get_capture_service()
        
        result = await capture_service.generate_pdf(
            url=url,
            format=format,
            landscape=landscape
        )
        
        if result.success:
            logger.info("PDF generated", url=url, api_key=api_key)
            return {
                "success": True,
                "file_path": result.file_path,
                "file_size": result.file_size,
                "processing_time": result.processing_time
            }
        else:
            logger.warning("PDF generation failed", url=url, error=result.error)
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error("PDF generation failed", url=url, error=str(e))
        raise HTTPException(status_code=500, detail="PDF generation failed")


@router.get("/browser/stats")
async def get_browser_stats(api_key: str = Depends(get_current_api_key)) -> Dict[str, Any]:
    """
    Get browser and capture service statistics.
    """
    try:
        capture_service = get_capture_service()
        stats = capture_service.get_capture_stats()
        
        return {
            "browser_enabled": True,  # Since we're in enhanced endpoints
            "capture_stats": stats
        }
        
    except Exception as e:
        logger.error("Failed to get browser stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get statistics")