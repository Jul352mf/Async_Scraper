"""
Database models for persistent storage.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import uuid4
import json

from scraper.api.models import JobStatus, JobType, JobProgress


class JobModel:
    """Database model for jobs."""
    
    def __init__(
        self,
        id: str,
        type: str,
        status: str,
        config: Dict[str, Any],
        created_at: datetime,
        updated_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        progress: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        result_count: Optional[int] = None,
    ):
        self.id = id
        self.type = type
        self.status = status
        self.config = config
        self.created_at = created_at
        self.updated_at = updated_at
        self.started_at = started_at
        self.completed_at = completed_at
        self.progress = progress or {}
        self.error_message = error_message
        self.result_count = result_count

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobModel":
        """Create JobModel from database row dictionary."""
        # Parse JSON fields
        config = json.loads(data["config"]) if isinstance(data["config"], str) else data["config"]
        progress = json.loads(data["progress"]) if data.get("progress") and isinstance(data["progress"], str) else data.get("progress") or {}
        
        return cls(
            id=data["id"],
            type=data["type"],
            status=data["status"],
            config=config,
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            progress=progress,
            error_message=data.get("error_message"),
            result_count=data.get("result_count"),
        )

    def to_api_model(self):
        """Convert to API Job model."""
        from scraper.api.models import Job
        
        return Job(
            id=self.id,
            type=JobType(self.type),
            status=JobStatus(self.status),
            config=self.config,
            created_at=self.created_at,
            updated_at=self.updated_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            progress=JobProgress(**self.progress) if self.progress else None,
            error_message=self.error_message,
            result_count=self.result_count,
        )


class JobResultModel:
    """Database model for job results."""
    
    def __init__(
        self,
        id: str,
        job_id: str,
        result_type: str,  # 'email' or 'domain'
        data: Dict[str, Any],
        created_at: datetime,
    ):
        self.id = id
        self.job_id = job_id
        self.result_type = result_type
        self.data = data
        self.created_at = created_at

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobResultModel":
        """Create JobResultModel from database row dictionary."""
        result_data = json.loads(data["data"]) if isinstance(data["data"], str) else data["data"]
        
        return cls(
            id=data["id"],
            job_id=data["job_id"],
            result_type=data["result_type"],
            data=result_data,
            created_at=data["created_at"],
        )

    def to_api_model(self):
        """Convert to API result model."""
        from scraper.api.models import EmailResult, DomainResult
        
        if self.result_type == "email":
            return EmailResult(**self.data)
        elif self.result_type == "domain":
            return DomainResult(**self.data)
        else:
            return self.data


class ProxyModel:
    """Database model for proxies."""
    
    def __init__(
        self,
        id: str,
        url: str,
        description: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        country: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_active: bool = True,
        health_status: str = "unknown",
        success_rate: float = 0.0,
        avg_response_time: Optional[float] = None,
        last_used: Optional[datetime] = None,
        last_health_check: Optional[datetime] = None,
        consecutive_failures: int = 0,
        is_blacklisted: bool = False,
        created_at: datetime = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.url = url
        self.description = description
        self.username = username
        self.password = password
        self.country = country
        self.tags = tags or []
        self.is_active = is_active
        self.health_status = health_status
        self.success_rate = success_rate
        self.avg_response_time = avg_response_time
        self.last_used = last_used
        self.last_health_check = last_health_check
        self.consecutive_failures = consecutive_failures
        self.is_blacklisted = is_blacklisted
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProxyModel":
        """Create ProxyModel from database row dictionary."""
        tags = json.loads(data["tags"]) if data.get("tags") and isinstance(data["tags"], str) else data.get("tags") or []
        
        return cls(
            id=data["id"],
            url=data["url"],
            description=data.get("description"),
            username=data.get("username"),
            password=data.get("password"),
            country=data.get("country"),
            tags=tags,
            is_active=data.get("is_active", True),
            health_status=data.get("health_status", "unknown"),
            success_rate=data.get("success_rate", 0.0),
            avg_response_time=data.get("avg_response_time"),
            last_used=data.get("last_used"),
            last_health_check=data.get("last_health_check"),
            consecutive_failures=data.get("consecutive_failures", 0),
            is_blacklisted=data.get("is_blacklisted", False),
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
        )

    def to_api_model(self):
        """Convert to API Proxy model."""
        from scraper.proxy.models import Proxy, ProxyHealth
        
        health = ProxyHealth(
            status=self.health_status,
            success_rate=self.success_rate,
            avg_response_time=self.avg_response_time,
            last_check=self.last_health_check,
            consecutive_failures=self.consecutive_failures,
            is_blacklisted=self.is_blacklisted,
        )
        
        return Proxy(
            id=self.id,
            url=self.url,
            description=self.description,
            username=self.username,
            password=self.password,
            country=self.country,
            tags=self.tags,
            is_active=self.is_active,
            health=health,
            last_used=self.last_used,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )