"""
Job Models

Pydantic models for job management and tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Job type enumeration."""
    SCRAPE_COMPANIES = "scrape_companies"
    SCRAPE_DOMAINS = "scrape_domains"


class JobProgress(BaseModel):
    """Job progress information."""
    model_config = ConfigDict(extra="forbid")
    
    total: int = Field(..., description="Total items to process")
    completed: int = Field(..., description="Items completed")
    failed: int = Field(default=0, description="Items failed")
    percent: float = Field(..., ge=0.0, le=100.0, description="Progress percentage")
    current_item: Optional[str] = Field(None, description="Currently processing item")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


class Job(BaseModel):
    """Core job model."""
    model_config = ConfigDict(extra="forbid")
    
    id: str = Field(..., description="Unique job identifier")
    type: JobType = Field(..., description="Job type")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current job status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    progress: Optional[JobProgress] = Field(None, description="Job progress information")
    config: Dict[str, Any] = Field(default_factory=dict, description="Job configuration")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    result_count: Optional[int] = Field(None, description="Number of results")


class JobCreate(BaseModel):
    """Model for job creation requests."""
    model_config = ConfigDict(extra="forbid")
    
    type: JobType = Field(..., description="Job type to create")
    config: Dict[str, Any] = Field(..., description="Job configuration parameters")


class JobResponse(BaseModel):
    """Standard job response model."""
    model_config = ConfigDict(extra="forbid")
    
    job: Job = Field(..., description="Job information")
    message: str = Field(..., description="Response message")


class EmailResult(BaseModel):
    """Email extraction result."""
    model_config = ConfigDict(extra="forbid")
    
    email: str = Field(..., description="Extracted email address")
    domain: str = Field(..., description="Source domain") 
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: str = Field(..., description="Source where email was found")
    verified: bool = Field(default=False, description="Whether email is verified")


class DomainResult(BaseModel):
    """Domain processing result."""
    model_config = ConfigDict(extra="forbid")
    
    domain: str = Field(..., description="Domain name")
    emails: List[EmailResult] = Field(default_factory=list, description="Extracted emails")
    status: str = Field(..., description="Processing status")
    error: Optional[str] = Field(None, description="Error message if failed")
    processing_time: float = Field(..., description="Processing time in seconds")


class JobResult(BaseModel):
    """Job result model."""
    model_config = ConfigDict(extra="forbid")
    
    job_id: str = Field(..., description="Job identifier")
    results: List[Union[EmailResult, DomainResult]] = Field(..., description="Job results")
    summary: Dict[str, Any] = Field(..., description="Result summary")
    generated_at: datetime = Field(..., description="Result generation timestamp")