"""Multi-tenant models and data structures."""

import time
import uuid
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field


class TenantStatus(Enum):
    """Tenant status options."""
    
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"
    DELETED = "deleted"


class TenantPlan(Enum):
    """Tenant subscription plans."""
    
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class TenantQuotas:
    """Resource quotas for a tenant."""
    
    # API request limits
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    requests_per_month: int = 100000
    
    # Job limits
    concurrent_jobs: int = 5
    max_jobs_per_day: int = 100
    job_retention_days: int = 30
    
    # Storage limits
    storage_mb: int = 1000
    max_file_size_mb: int = 100
    
    # Feature limits
    javascript_enabled: bool = False
    proxy_enabled: bool = False
    custom_headers: bool = True
    webhook_enabled: bool = False
    
    # Rate limiting
    burst_requests: int = 100
    sustained_rps: int = 10
    

@dataclass
class TenantUsage:
    """Current usage statistics for a tenant."""
    
    # API usage
    requests_this_hour: int = 0
    requests_this_day: int = 0
    requests_this_month: int = 0
    
    # Job usage
    active_jobs: int = 0
    jobs_this_day: int = 0
    total_jobs: int = 0
    
    # Storage usage
    storage_used_mb: float = 0.0
    
    # Last reset timestamps
    hour_reset: float = field(default_factory=time.time)
    day_reset: float = field(default_factory=time.time)
    month_reset: float = field(default_factory=time.time)
    

class TenantConfig(BaseModel):
    """Tenant configuration."""
    
    # Basic info
    tenant_id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Tenant name")
    description: Optional[str] = Field(None, description="Tenant description")
    
    # Status and plan
    status: TenantStatus = Field(TenantStatus.ACTIVE, description="Tenant status")
    plan: TenantPlan = Field(TenantPlan.FREE, description="Subscription plan")
    
    # Contact info
    contact_email: str = Field(..., description="Primary contact email")
    organization: Optional[str] = Field(None, description="Organization name")
    
    # Settings
    timezone: str = Field("UTC", description="Default timezone")
    webhook_url: Optional[str] = Field(None, description="Webhook endpoint URL")
    custom_domain: Optional[str] = Field(None, description="Custom domain")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: Optional[datetime] = Field(None, description="Last API activity")
    
    # Tags for organization
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True


class TenantModel:
    """Tenant data model with quotas and usage tracking."""
    
    def __init__(
        self,
        tenant_id: str,
        config: TenantConfig,
        quotas: Optional[TenantQuotas] = None,
        usage: Optional[TenantUsage] = None
    ):
        self.tenant_id = tenant_id
        self.config = config
        self.quotas = quotas or self._default_quotas_for_plan(config.plan)
        self.usage = usage or TenantUsage()
        
    @classmethod
    def create_new(
        cls,
        name: str,
        contact_email: str,
        plan: TenantPlan = TenantPlan.FREE,
        **kwargs
    ) -> "TenantModel":
        """Create a new tenant."""
        tenant_id = str(uuid.uuid4())
        
        config = TenantConfig(
            tenant_id=tenant_id,
            name=name,
            contact_email=contact_email,
            plan=plan,
            **kwargs
        )
        
        return cls(tenant_id, config)
        
    def _default_quotas_for_plan(self, plan: TenantPlan) -> TenantQuotas:
        """Get default quotas for a subscription plan."""
        if plan == TenantPlan.FREE:
            return TenantQuotas(
                requests_per_hour=100,
                requests_per_day=1000,
                requests_per_month=10000,
                concurrent_jobs=2,
                max_jobs_per_day=10,
                storage_mb=100,
                javascript_enabled=False,
                proxy_enabled=False,
                burst_requests=20,
                sustained_rps=2
            )
        elif plan == TenantPlan.BASIC:
            return TenantQuotas(
                requests_per_hour=1000,
                requests_per_day=10000,
                requests_per_month=100000,
                concurrent_jobs=5,
                max_jobs_per_day=100,
                storage_mb=1000,
                javascript_enabled=True,
                proxy_enabled=False,
                burst_requests=100,
                sustained_rps=10
            )
        elif plan == TenantPlan.PROFESSIONAL:
            return TenantQuotas(
                requests_per_hour=5000,
                requests_per_day=50000,
                requests_per_month=1000000,
                concurrent_jobs=20,
                max_jobs_per_day=500,
                storage_mb=10000,
                javascript_enabled=True,
                proxy_enabled=True,
                burst_requests=500,
                sustained_rps=50
            )
        else:  # ENTERPRISE
            return TenantQuotas(
                requests_per_hour=25000,
                requests_per_day=500000,
                requests_per_month=10000000,
                concurrent_jobs=100,
                max_jobs_per_day=5000,
                storage_mb=100000,
                javascript_enabled=True,
                proxy_enabled=True,
                webhook_enabled=True,
                burst_requests=2000,
                sustained_rps=200
            )
            
    def is_active(self) -> bool:
        """Check if tenant is active."""
        return self.config.status == TenantStatus.ACTIVE
        
    def can_make_request(self) -> bool:
        """Check if tenant can make an API request."""
        if not self.is_active():
            return False
            
        # Check quotas
        if self.usage.requests_this_hour >= self.quotas.requests_per_hour:
            return False
        if self.usage.requests_this_day >= self.quotas.requests_per_day:
            return False
        if self.usage.requests_this_month >= self.quotas.requests_per_month:
            return False
            
        return True
        
    def can_create_job(self) -> bool:
        """Check if tenant can create a new job."""
        if not self.is_active():
            return False
            
        # Check concurrent job limit
        if self.usage.active_jobs >= self.quotas.concurrent_jobs:
            return False
            
        # Check daily job limit
        if self.usage.jobs_this_day >= self.quotas.max_jobs_per_day:
            return False
            
        return True
        
    def has_feature(self, feature: str) -> bool:
        """Check if tenant has access to a feature."""
        feature_mapping = {
            "javascript": self.quotas.javascript_enabled,
            "proxy": self.quotas.proxy_enabled,
            "webhook": self.quotas.webhook_enabled,
            "custom_headers": self.quotas.custom_headers,
        }
        
        return feature_mapping.get(feature, False)
        
    def record_request(self) -> None:
        """Record an API request."""
        current_time = time.time()
        
        # Reset counters if needed
        if current_time - self.usage.hour_reset >= 3600:
            self.usage.requests_this_hour = 0
            self.usage.hour_reset = current_time
            
        if current_time - self.usage.day_reset >= 86400:
            self.usage.requests_this_day = 0
            self.usage.day_reset = current_time
            
        if current_time - self.usage.month_reset >= 2592000:  # 30 days
            self.usage.requests_this_month = 0
            self.usage.month_reset = current_time
            
        # Increment counters
        self.usage.requests_this_hour += 1
        self.usage.requests_this_day += 1
        self.usage.requests_this_month += 1
        
        # Update last activity
        self.config.last_activity = datetime.utcnow()
        
    def record_job_start(self) -> None:
        """Record a job starting."""
        self.usage.active_jobs += 1
        self.usage.jobs_this_day += 1
        self.usage.total_jobs += 1
        
    def record_job_end(self) -> None:
        """Record a job ending."""
        if self.usage.active_jobs > 0:
            self.usage.active_jobs -= 1
            
    def get_usage_percentage(self) -> Dict[str, float]:
        """Get usage as percentage of quotas."""
        return {
            "requests_hour": (self.usage.requests_this_hour / self.quotas.requests_per_hour) * 100,
            "requests_day": (self.usage.requests_this_day / self.quotas.requests_per_day) * 100,
            "requests_month": (self.usage.requests_this_month / self.quotas.requests_per_month) * 100,
            "concurrent_jobs": (self.usage.active_jobs / self.quotas.concurrent_jobs) * 100,
            "jobs_day": (self.usage.jobs_this_day / self.quotas.max_jobs_per_day) * 100,
            "storage": (self.usage.storage_used_mb / self.quotas.storage_mb) * 100,
        }
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "config": self.config.dict(),
            "quotas": {
                "requests_per_hour": self.quotas.requests_per_hour,
                "requests_per_day": self.quotas.requests_per_day,
                "requests_per_month": self.quotas.requests_per_month,
                "concurrent_jobs": self.quotas.concurrent_jobs,
                "max_jobs_per_day": self.quotas.max_jobs_per_day,
                "job_retention_days": self.quotas.job_retention_days,
                "storage_mb": self.quotas.storage_mb,
                "max_file_size_mb": self.quotas.max_file_size_mb,
                "javascript_enabled": self.quotas.javascript_enabled,
                "proxy_enabled": self.quotas.proxy_enabled,
                "custom_headers": self.quotas.custom_headers,
                "webhook_enabled": self.quotas.webhook_enabled,
                "burst_requests": self.quotas.burst_requests,
                "sustained_rps": self.quotas.sustained_rps,
            },
            "usage": {
                "requests_this_hour": self.usage.requests_this_hour,
                "requests_this_day": self.usage.requests_this_day,
                "requests_this_month": self.usage.requests_this_month,
                "active_jobs": self.usage.active_jobs,
                "jobs_this_day": self.usage.jobs_this_day,
                "total_jobs": self.usage.total_jobs,
                "storage_used_mb": self.usage.storage_used_mb,
            },
            "usage_percentage": self.get_usage_percentage()
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TenantModel":
        """Create from dictionary."""
        config = TenantConfig(**data["config"])
        
        quotas = TenantQuotas(**data["quotas"])
        usage = TenantUsage(**data["usage"])
        
        return cls(
            tenant_id=data["tenant_id"],
            config=config,
            quotas=quotas,
            usage=usage
        )