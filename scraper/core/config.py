"""Configuration management with pydantic."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheConfig(BaseModel):
    """Cache configuration settings."""
    
    l1_enabled: bool = Field(True, description="Enable L1 in-memory cache")
    l1_max_size: int = Field(1000, description="Maximum L1 cache entries")
    l1_ttl: int = Field(3600, description="L1 cache TTL in seconds")
    
    l2_enabled: bool = Field(False, description="Enable L2 Redis cache")
    l2_redis_url: str = Field("redis://localhost:6379", description="Redis connection URL")
    l2_ttl: int = Field(86400, description="L2 cache TTL in seconds")
    
    l3_enabled: bool = Field(False, description="Enable L3 PostgreSQL cache")
    l3_postgres_url: str = Field("postgresql://localhost:5432/scraper", description="PostgreSQL connection URL")
    l3_ttl: int = Field(604800, description="L3 cache TTL in seconds")


class ConcurrencyConfig(BaseModel):
    """Concurrency and rate limiting configuration."""
    
    max_concurrent_domains: int = Field(10, description="Maximum concurrent domains to process")
    max_concurrent_per_domain: int = Field(5, description="Maximum concurrent requests per domain")
    max_queue_size: int = Field(1000, description="Maximum queue size for backpressure")
    
    global_rate_limit: float = Field(2.0, description="Global requests per second")
    domain_rate_limit: float = Field(1.0, description="Per-domain requests per second")
    
    retry_max_attempts: int = Field(3, description="Maximum retry attempts")
    retry_backoff_factor: float = Field(2.0, description="Exponential backoff factor")
    retry_max_delay: float = Field(60.0, description="Maximum retry delay in seconds")


class ScrapingConfig(BaseModel):
    """Web scraping configuration."""
    
    user_agents: List[str] = Field(
        default=[
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ],
        description="List of user agents to rotate"
    )
    
    timeout: float = Field(30.0, description="Request timeout in seconds")
    max_redirects: int = Field(10, description="Maximum redirects to follow")
    
    use_playwright_fallback: bool = Field(True, description="Use Playwright for JS-heavy sites")
    playwright_timeout: float = Field(60.0, description="Playwright timeout in seconds")
    
    max_crawl_depth: int = Field(3, description="Maximum crawl depth")
    max_pages_per_domain: int = Field(50, description="Maximum pages to crawl per domain")
    
    respect_robots_txt: bool = Field(True, description="Respect robots.txt directives")
    crawl_delay: float = Field(1.0, description="Default crawl delay in seconds")


class ProxyConfig(BaseModel):
    """Proxy configuration."""
    
    enabled: bool = Field(False, description="Enable proxy usage")
    proxy_urls: List[str] = Field(default=[], description="List of proxy URLs")
    rotate_proxies: bool = Field(True, description="Rotate between proxies")
    proxy_timeout: float = Field(30.0, description="Proxy timeout in seconds")


class EmailConfig(BaseModel):
    """Email extraction and validation configuration."""
    
    extract_emails: bool = Field(True, description="Enable email extraction")
    validate_syntax: bool = Field(True, description="Perform basic syntax validation")
    validate_external: bool = Field(False, description="Use external validation service")
    external_validator_api_key: Optional[str] = Field(None, description="External validator API key")
    
    decode_obfuscation: bool = Field(True, description="Decode obfuscated emails")
    min_confidence_score: float = Field(0.7, description="Minimum confidence score for emails")


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field("INFO", description="Logging level")
    format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format")
    file_enabled: bool = Field(True, description="Enable file logging")
    file_path: str = Field("logs/scraper.log", description="Log file path")
    max_file_size: int = Field(10485760, description="Maximum log file size in bytes")
    backup_count: int = Field(5, description="Number of log file backups")
    
    @field_validator("level")
    @classmethod
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()


class Config(BaseSettings):
    """Main configuration class."""
    
    # General settings
    debug: bool = Field(False, description="Enable debug mode")
    verbose: bool = Field(False, description="Enable verbose output")
    
    # Component configurations
    cache: CacheConfig = Field(default_factory=CacheConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # Input/Output settings
    input_file: Optional[str] = Field(None, description="Input file path")
    output_file: Optional[str] = Field(None, description="Output file path")
    output_format: str = Field("csv", description="Output format (csv, xlsx, json)")
    
    # Progress and UX
    show_progress: bool = Field(True, description="Show progress bars")
    progress_update_interval: float = Field(1.0, description="Progress update interval in seconds")
    
    # Performance settings
    max_memory_mb: int = Field(1024, description="Maximum memory usage in MB")
    
    model_config = SettingsConfigDict(
        env_prefix="SCRAPER_",
        env_file=".env",
        case_sensitive=False
    )
    
    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v):
        valid_formats = ["csv", "xlsx", "json"]
        if v.lower() not in valid_formats:
            raise ValueError(f"Output format must be one of {valid_formats}")
        return v.lower()
    
    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save configuration to file."""
        with open(file_path, "w") as f:
            f.write(self.model_dump_json(indent=2))
    
    @classmethod
    def load_from_file(cls, file_path: Union[str, Path]) -> "Config":
        """Load configuration from file."""
        with open(file_path, "r") as f:
            config_data = f.read()
        return cls.model_validate_json(config_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.model_dump()


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config


def load_config(file_path: Optional[Union[str, Path]] = None) -> Config:
    """Load configuration from file or environment."""
    if file_path and os.path.exists(file_path):
        config = Config.load_from_file(file_path)
    else:
        config = Config()
    
    set_config(config)
    return config