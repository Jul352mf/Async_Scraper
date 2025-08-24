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
    
    @property
    def user_agent(self) -> str:
        """Get the first user agent as default."""
        return self.user_agents[0] if self.user_agents else "Mozilla/5.0 AsyncScraper/1.0"
    
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
    rotation_strategy: str = Field("round_robin", description="Proxy rotation strategy")
    health_check_interval: int = Field(300, description="Health check interval in seconds")
    health_check_timeout: int = Field(10, description="Health check timeout in seconds")
    health_check_url: str = Field("http://httpbin.org/ip", description="URL for health checks")
    max_consecutive_failures: int = Field(3, description="Max failures before blacklisting")
    blacklist_duration: int = Field(1800, description="Blacklist duration in seconds")
    fallback_to_direct: bool = Field(True, description="Fallback to direct connection")
    retry_failed_proxies: bool = Field(True, description="Retry failed proxies after cooldown")
    geographic_preference: Optional[str] = Field(None, description="Preferred proxy country")
    
    @field_validator("rotation_strategy")
    @classmethod
    def validate_rotation_strategy(cls, v):
        valid_strategies = ["round_robin", "random", "least_used", "fastest", "geographic"]
        if v.lower() not in valid_strategies:
            raise ValueError(f"Rotation strategy must be one of {valid_strategies}")
        return v.lower()


class EmailConfig(BaseModel):
    """Email extraction and validation configuration."""
    
    extract_emails: bool = Field(True, description="Enable email extraction")
    validate_syntax: bool = Field(True, description="Perform basic syntax validation")
    validate_external: bool = Field(False, description="Use external validation service")
    external_validator_api_key: Optional[str] = Field(None, description="External validator API key")
    
    decode_obfuscation: bool = Field(True, description="Decode obfuscated emails")
    min_confidence_score: float = Field(0.7, description="Minimum confidence score for emails")


class BrowserConfig(BaseModel):
    """Browser and JavaScript scraping configuration."""
    
    enabled: bool = Field(True, description="Enable browser-based scraping")
    browser_type: str = Field("chromium", description="Browser type (chromium, firefox, webkit)")
    headless: bool = Field(True, description="Run browser in headless mode")
    show_browser: bool = Field(False, description="Show browser window (overrides headless)")
    
    max_browsers: int = Field(3, description="Maximum number of browser instances")
    max_contexts_per_browser: int = Field(10, description="Maximum contexts per browser")
    
    timeout: float = Field(60.0, description="Browser operation timeout in seconds")
    navigation_timeout: float = Field(30.0, description="Page navigation timeout in seconds")
    
    viewport_width: int = Field(1920, description="Browser viewport width")
    viewport_height: int = Field(1080, description="Browser viewport height")
    
    load_images: bool = Field(False, description="Load images in browser")
    javascript_enabled: bool = Field(True, description="Enable JavaScript execution")
    
    screenshot_enabled: bool = Field(True, description="Enable screenshot capture")
    screenshot_format: str = Field("png", description="Screenshot format (png, jpeg)")
    screenshot_quality: int = Field(80, description="Screenshot quality (1-100)")
    
    pdf_enabled: bool = Field(True, description="Enable PDF generation")
    pdf_format: str = Field("A4", description="PDF paper format")
    
    @field_validator("browser_type")
    @classmethod
    def validate_browser_type(cls, v):
        valid_types = ["chromium", "firefox", "webkit"]
        if v.lower() not in valid_types:
            raise ValueError(f"Browser type must be one of {valid_types}")
        return v.lower()
    
    @field_validator("screenshot_format")
    @classmethod
    def validate_screenshot_format(cls, v):
        valid_formats = ["png", "jpeg"]
        if v.lower() not in valid_formats:
            raise ValueError(f"Screenshot format must be one of {valid_formats}")
        return v.lower()


class ApiConfig(BaseModel):
    """API server configuration."""
    
    host: str = Field("0.0.0.0", description="API server host")
    port: int = Field(8000, description="API server port")
    debug: bool = Field(False, description="Enable API debug mode")
    
    api_keys: List[str] = Field(
        default=["test-api-key-123456"],
        description="Valid API keys for authentication"
    )
    
    rate_limit_per_minute: int = Field(100, description="Requests per minute per API key")
    rate_limit_burst: int = Field(20, description="Burst limit for rate limiting")
    
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    cors_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE"], description="CORS allowed methods")
    
    docs_enabled: bool = Field(True, description="Enable OpenAPI docs")
    docs_url: str = Field("/docs", description="OpenAPI docs URL")
    redoc_url: str = Field("/redoc", description="ReDoc documentation URL")
    
    websocket_enabled: bool = Field(True, description="Enable WebSocket support")
    websocket_path: str = Field("/api/v1/ws", description="WebSocket endpoint path")
    
    job_cleanup_interval: int = Field(300, description="Job cleanup interval in seconds")
    job_max_age: int = Field(86400, description="Maximum job age in seconds before cleanup")
    
    @field_validator("api_keys")
    @classmethod
    def validate_api_keys(cls, v):
        for key in v:
            if len(key) < 8:
                raise ValueError("API keys must be at least 8 characters long")
        return v


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
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
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