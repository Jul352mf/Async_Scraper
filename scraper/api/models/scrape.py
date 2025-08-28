"""
Scraping Models

Pydantic models for scraping API requests and responses.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, HttpUrl


class ScrapeCompaniesRequest(BaseModel):
    """Request model for scraping companies."""
    model_config = ConfigDict(extra="forbid")
    
    companies: List[str] = Field(..., min_length=1, description="List of company names to scrape")
    max_emails_per_company: int = Field(default=10, ge=1, le=100, description="Maximum emails per company")
    include_subdomains: bool = Field(default=True, description="Include subdomains in search")
    verify_emails: bool = Field(default=False, description="Verify email deliverability")
    timeout: Optional[int] = Field(default=None, ge=1, le=300, description="Request timeout in seconds")
    custom_config: Optional[Dict[str, Any]] = Field(default=None, description="Custom scraping configuration")


class ScrapeDomainsRequest(BaseModel):
    """Request model for scraping domains."""
    model_config = ConfigDict(extra="forbid")
    
    domains: List[str] = Field(..., min_length=1, description="List of domains to scrape")
    max_emails_per_domain: int = Field(default=10, ge=1, le=100, description="Maximum emails per domain")
    crawl_depth: int = Field(default=2, ge=1, le=5, description="Maximum crawl depth")
    verify_emails: bool = Field(default=False, description="Verify email deliverability") 
    timeout: Optional[int] = Field(default=None, ge=1, le=300, description="Request timeout in seconds")
    custom_config: Optional[Dict[str, Any]] = Field(default=None, description="Custom scraping configuration")


class ScrapeResponse(BaseModel):
    """Response model for scraping requests."""
    model_config = ConfigDict(extra="forbid")
    
    job_id: str = Field(..., description="Created job identifier")
    status: str = Field(..., description="Initial job status") 
    message: str = Field(..., description="Response message")
    estimated_duration: Optional[str] = Field(None, description="Estimated completion time")
    webhook_url: Optional[HttpUrl] = Field(None, description="Webhook for completion notification")


class BulkScrapeRequest(BaseModel):
    """Request model for bulk scraping operations."""
    model_config = ConfigDict(extra="forbid")
    
    targets: List[str] = Field(..., min_length=1, description="List of targets (companies or domains)")
    scrape_type: str = Field(..., description="Type of scraping (companies or domains)")
    batch_size: int = Field(default=10, ge=1, le=50, description="Batch processing size")
    priority: int = Field(default=5, ge=1, le=10, description="Job priority (1=lowest, 10=highest)")
    webhook_url: Optional[HttpUrl] = Field(None, description="Webhook for completion notification")
    custom_config: Optional[Dict[str, Any]] = Field(default=None, description="Custom scraping configuration")