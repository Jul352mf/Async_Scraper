"""
Proxy models and data structures.
"""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from pydantic import BaseModel, Field, validator


class ProxyType(str, Enum):
    """Supported proxy types."""
    HTTP = "http"
    HTTPS = "https" 
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class ProxyRotationStrategy(str, Enum):
    """Proxy rotation strategies."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_USED = "least_used"
    FASTEST = "fastest"
    GEOGRAPHIC = "geographic"


class ProxyStatus(str, Enum):
    """Proxy health status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    CHECKING = "checking"
    BLACKLISTED = "blacklisted"
    UNKNOWN = "unknown"


class ProxyHealth(BaseModel):
    """Proxy health information."""
    status: ProxyStatus = ProxyStatus.UNKNOWN
    last_checked: Optional[datetime] = None
    response_time: Optional[float] = None  # in seconds
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    error_message: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100
    
    @property
    def is_healthy(self) -> bool:
        """Check if proxy is considered healthy."""
        return (
            self.status == ProxyStatus.HEALTHY and
            self.consecutive_failures < 3 and
            self.success_rate > 50.0
        )


class Proxy(BaseModel):
    """Proxy configuration and metadata."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    proxy_type: Optional[ProxyType] = None
    host: Optional[str] = None  
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    health: ProxyHealth = Field(default_factory=ProxyHealth)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    use_count: int = 0
    enabled: bool = True
    
    @validator('url')
    def validate_url(cls, v):
        """Validate proxy URL format."""
        try:
            parsed = urlparse(v)
            if not parsed.scheme or not parsed.hostname:
                raise ValueError("Invalid proxy URL format")
            return v
        except Exception as e:
            raise ValueError(f"Invalid proxy URL: {e}")
    
    @validator('proxy_type', pre=True, always=True)
    def set_proxy_type_from_url(cls, v, values):
        """Infer proxy type from URL if not provided."""
        if v is not None:
            return v
        
        url = values.get('url')
        if url:
            scheme = urlparse(url).scheme.lower()
            if scheme in ['http', 'https']:
                return ProxyType.HTTP
            elif scheme in ['socks4']:
                return ProxyType.SOCKS4
            elif scheme in ['socks5']:
                return ProxyType.SOCKS5
        
        return ProxyType.HTTP
    
    @validator('host', pre=True, always=True)
    def set_host_from_url(cls, v, values):
        """Extract host from URL if not provided."""
        if v is not None:
            return v
        
        url = values.get('url')
        if url:
            return urlparse(url).hostname
        return v
    
    @validator('port', pre=True, always=True)
    def set_port_from_url(cls, v, values):
        """Extract port from URL if not provided."""
        if v is not None:
            return v
        
        url = values.get('url')
        if url:
            parsed = urlparse(url)
            if parsed.port:
                return parsed.port
            # Default ports
            if parsed.scheme == 'http':
                return 80
            elif parsed.scheme == 'https':
                return 443
            elif parsed.scheme in ['socks4', 'socks5']:
                return 1080
        return v
    
    def to_dict(self, include_credentials: bool = False) -> Dict[str, Any]:
        """Convert to dictionary format suitable for aiohttp/playwright."""
        proxy_dict = {
            "server": f"{self.effective_proxy_type.value}://{self.effective_host}:{self.effective_port}"
        }
        
        if include_credentials and self.username and self.password:
            proxy_dict.update({
                "username": self.username,
                "password": self.password
            })
        
        return proxy_dict
    
    @property
    def effective_host(self) -> str:
        """Get the effective host (never None)."""
        return self.host or "unknown"
    
    @property
    def effective_port(self) -> int:
        """Get the effective port (never None)."""
        return self.port or 80
    
    @property
    def effective_proxy_type(self) -> ProxyType:
        """Get the effective proxy type (never None)."""
        return self.proxy_type or ProxyType.HTTP
    
    def mark_used(self) -> None:
        """Mark proxy as used."""
        self.last_used = datetime.utcnow()
        self.use_count += 1
    
    def update_health(self, success: bool, response_time: Optional[float] = None, error: Optional[str] = None) -> None:
        """Update proxy health status."""
        self.health.last_checked = datetime.utcnow()
        
        if success:
            self.health.success_count += 1
            self.health.consecutive_failures = 0
            self.health.status = ProxyStatus.HEALTHY
            self.health.error_message = None
            if response_time:
                self.health.response_time = response_time
        else:
            self.health.failure_count += 1
            self.health.consecutive_failures += 1
            self.health.error_message = error
            
            if self.health.consecutive_failures >= 5:
                self.health.status = ProxyStatus.BLACKLISTED
            else:
                self.health.status = ProxyStatus.UNHEALTHY


class ProxyConfig(BaseModel):
    """Configuration for proxy system."""
    enabled: bool = True
    rotation_strategy: ProxyRotationStrategy = ProxyRotationStrategy.ROUND_ROBIN
    health_check_interval: int = 300  # seconds
    health_check_timeout: int = 10  # seconds
    health_check_url: str = "http://httpbin.org/ip"
    max_consecutive_failures: int = 3
    blacklist_duration: int = 1800  # seconds (30 minutes)
    fallback_to_direct: bool = True
    retry_failed_proxies: bool = True
    geographic_preference: Optional[str] = None
    
    class Config:
        """Pydantic config."""
        validate_assignment = True