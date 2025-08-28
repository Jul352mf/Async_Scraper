"""
API Models

This package contains Pydantic models for API requests and responses.
"""

from .jobs import *
from .scrape import *

__all__ = [
    # Job models
    "Job",
    "JobStatus", 
    "JobType",
    "JobCreate",
    "JobResponse",
    "JobResult",
    "JobProgress",
    "EmailResult",
    "DomainResult",
    
    # Scrape models
    "ScrapeCompaniesRequest",
    "ScrapeDomainsRequest", 
    "ScrapeResponse",
    "BulkScrapeRequest",
]