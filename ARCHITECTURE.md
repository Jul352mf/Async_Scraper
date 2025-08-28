# Async_Scraper Architecture Guide

## Overview

Async_Scraper is a production-ready, async-first web scraping framework that combines high-performance CLI tools with a comprehensive REST API platform. The architecture is designed for scalability, maintainability, and enterprise integration.

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Async_Scraper Platform                      │
├─────────────────────┬───────────────────────────────────────────┤
│                     │                                           │
│   CLI Interface     │            REST API Server               │
│                     │                                           │
│  ┌─────────────────┐│  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Command Line    ││  │ FastAPI     │  │ WebSocket           │ │
│  │ Tools           ││  │ Endpoints   │  │ Real-time Updates   │ │
│  └─────────────────┘│  └─────────────┘  └─────────────────────┘ │
└─────────────────────┼───────────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────────┐
│                     Core Services Layer                        │
│                                                                 │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ Scraper     │ │ Email       │ │ Web Client  │ │ Job         │ │
│ │ Manager     │ │ Extractor   │ │ Service     │ │ Manager     │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                        │
│                                                                 │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ Multi-layer │ │ Rate        │ │ Config      │ │ Logging &   │ │
│ │ Caching     │ │ Limiting    │ │ Management  │ │ Monitoring  │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Core Architecture Principles

### 1. Async-First Design
- All I/O operations use async/await patterns
- aiohttp for HTTP requests with connection pooling
- Async database connections and transactions
- Non-blocking WebSocket connections

### 2. Modular Architecture
- Clean separation of concerns across layers
- Dependency injection for testability
- Interface-based design for extensibility

### 3. Configuration-Driven
- Pydantic models for type-safe configuration
- Environment variable support
- Hierarchical configuration loading

### 4. Production-Ready Features
- Comprehensive error handling and logging
- Multi-layer caching for performance
- Rate limiting and backpressure management
- API key authentication and authorization

## Directory Structure

```
scraper/
├── api/                    # REST API Implementation
│   ├── main.py            # FastAPI application
│   ├── job_manager.py     # Background job management
│   ├── middleware/        # Authentication, rate limiting
│   ├── models/           # Pydantic request/response models
│   └── routes/           # API endpoint implementations
├── cli/                   # Command Line Interface
│   ├── __init__.py       # CLI entry points
│   └── commands.py       # Command implementations
├── core/                  # Core Infrastructure
│   ├── config.py         # Configuration management
│   ├── logger.py         # Structured logging
│   ├── cache.py          # Multi-layer caching
│   └── utils.py          # Shared utilities
├── data/                  # Data Processing
│   ├── loader.py         # CSV/data file loading
│   ├── cleaner.py        # Data cleaning and validation
│   └── saver.py          # Result output handling
└── services/              # Business Logic
    ├── scraper_manager.py # Main scraping orchestration
    ├── email_extractor.py # Email extraction logic
    ├── domain_processor.py# Domain crawling
    └── web_client.py     # HTTP client abstraction
```

## API Architecture

### REST API Design

The API follows RESTful principles with the following endpoint structure:

```
GET  /health                          # Basic health check
GET  /health/detailed                 # Detailed health with metrics
POST /api/v1/scrape/companies         # Create company scraping job
POST /api/v1/scrape/domains           # Create domain crawling job
GET  /api/v1/jobs                     # List all jobs
GET  /api/v1/jobs/{job_id}           # Get job status and details
GET  /api/v1/jobs/{job_id}/results   # Get job results
POST /api/v1/jobs/{job_id}/cancel    # Cancel running job
DELETE /api/v1/jobs/{job_id}         # Delete completed job
WS   /api/v1/ws                      # WebSocket for real-time updates
```

### Authentication & Authorization

```python
# API Key Authentication
X-API-Key: your-secret-api-key

# Rate limiting per API key
- 100 requests per minute default
- Configurable limits per key
- Exponential backoff on rate limit exceeded
```

### Job Management System

```python
# Job Lifecycle
PENDING → RUNNING → COMPLETED
    ↓         ↓         ↑
CANCELLED ← ERROR  ← FAILED

# Job Types
- SCRAPE_COMPANIES: Extract emails from company websites
- SCRAPE_DOMAINS: Crawl domains with configurable depth
```

### WebSocket Real-time Updates

```javascript
// Connection with authentication
ws://localhost:8000/api/v1/ws?api_key=your-key

// Message Protocol
{
    "action": "subscribe",
    "job_id": "uuid-here"
}

// Progress Updates
{
    "type": "job_update",
    "job_id": "uuid-here",
    "job": {
        "status": "running",
        "progress": {
            "percent": 45.5,
            "current_item": "example.com",
            "total_items": 100,
            "completed_items": 45
        }
    }
}
```

## Core Services

### 1. Scraper Manager

**Purpose**: Orchestrates the entire scraping workflow
**Key Features**:
- Manages concurrent domain processing
- Handles rate limiting and backpressure
- Coordinates email extraction across multiple sources
- Provides progress tracking and status updates

```python
from scraper.services.scraper_manager import ScraperManager
from scraper.core.config import get_config

async def scrape_companies(companies: List[str]) -> List[Dict]:
    config = get_config()
    manager = ScraperManager(config)
    
    results = await manager.scrape_companies(
        companies=companies,
        max_emails_per_company=config.scraping.max_emails_per_company
    )
    return results
```

### 2. Email Extractor

**Purpose**: Finds and validates email addresses from web content
**Key Features**:
- Pattern-based email detection with regex
- Domain validation and filtering
- Duplicate elimination
- Format standardization

```python
from scraper.services.email_extractor import EmailExtractor

extractor = EmailExtractor()
emails = await extractor.extract_from_text(html_content)
emails = await extractor.extract_from_url("https://example.com")
```

### 3. Web Client Service

**Purpose**: Handles all HTTP operations with resilience
**Key Features**:
- Connection pooling for efficiency
- Automatic retry logic with exponential backoff
- Request/response logging
- Error handling and circuit breakers

```python
from scraper.services.web_client import WebClientService

async with WebClientService() as client:
    content = await client.get_page_content("https://example.com")
    if content:
        # Process content
        pass
```

### 4. Job Manager

**Purpose**: Manages background job processing for the API
**Key Features**:
- UUID-based job tracking
- Status management and persistence
- Progress monitoring
- Resource cleanup

```python
from scraper.api.job_manager import get_job_manager

job_manager = get_job_manager()
job = job_manager.create_job(JobType.SCRAPE_COMPANIES, {
    "companies": ["Google", "Microsoft"],
    "max_emails_per_company": 10
})

await job_manager.start_job(job.id)
status = job_manager.get_job_status(job.id)
```

## Configuration Management

### Configuration Hierarchy

1. **Environment Variables** (highest priority)
2. **Configuration Files** (.env, config.json)
3. **Default Values** (lowest priority)

### Configuration Structure

```python
from scraper.core.config import Config

config = Config(
    debug=False,
    cache=CacheConfig(
        l1_enabled=True,
        l1_max_size=1000,
        l2_enabled=False
    ),
    concurrency=ConcurrencyConfig(
        max_concurrent_domains=10,
        max_concurrent_per_domain=5,
        global_rate_limit=2.0
    ),
    scraping=ScrapingConfig(
        timeout=30.0,
        max_crawl_depth=3,
        respect_robots_txt=True
    ),
    api=ApiConfig(
        host="0.0.0.0",
        port=8000,
        api_keys=["test-api-key-123456"]
    )
)
```

## Caching Architecture

### Multi-Layer Caching System

```
L1 Cache (In-Memory)     L2 Cache (Redis)      L3 Cache (Disk)
┌─────────────────┐     ┌─────────────────┐    ┌─────────────────┐
│ Fast Access     │────▶│ Shared Storage  │───▶│ Persistent      │
│ 1000 entries    │     │ TTL-based       │    │ Long-term       │
│ LRU eviction    │     │ Cross-instance  │    │ Historical data │
└─────────────────┘     └─────────────────┘    └─────────────────┘
```

### Cache Usage Patterns

```python
from scraper.core.cache import get_cache_manager

cache = get_cache_manager()

# L1 - Fast in-memory lookup
email_pattern = await cache.get_l1(f"emails:{domain}")

# L2 - Redis-based shared cache
domain_content = await cache.get_l2(f"content:{url_hash}")

# L3 - Persistent disk cache
historical_data = await cache.get_l3(f"history:{company}")
```

## Error Handling & Resilience

### Error Handling Patterns

```python
import structlog
from scraper.core.logger import get_logger

logger = get_logger(__name__)

async def resilient_operation():
    try:
        result = await risky_operation()
        return result
    except aiohttp.ClientTimeout:
        logger.warning("Operation timeout", operation="risky_operation")
        return None
    except aiohttp.ClientError as e:
        logger.error("HTTP error", error=str(e))
        return None
    except Exception as e:
        logger.error("Unexpected error", error=str(e))
        raise
```

### Rate Limiting & Backpressure

```python
import asyncio
from asyncio import Semaphore

class RateLimiter:
    def __init__(self, rate: float):
        self.rate = rate
        self.semaphore = Semaphore(int(rate))
    
    async def acquire(self):
        await self.semaphore.acquire()
        await asyncio.sleep(1.0 / self.rate)
        self.semaphore.release()
```

## Testing Architecture

### Test Structure

```
tests/
├── unit/                  # Unit tests for individual components
│   ├── test_core.py      # Core infrastructure tests
│   ├── test_services.py  # Business logic tests
│   └── test_data.py      # Data processing tests
├── integration/          # Integration tests
│   ├── test_api.py       # API endpoint tests
│   └── test_scraping_api.py # Scraping workflow tests
└── fixtures/             # Test data and utilities
```

### Testing Patterns

```python
import pytest
from aioresponses import aioresponses

@pytest.mark.asyncio
async def test_email_extraction():
    with aioresponses() as mock:
        mock.get(
            "https://example.com",
            payload={"content": "<p>Contact: test@example.com</p>"}
        )
        
        extractor = EmailExtractor()
        emails = await extractor.extract_from_url("https://example.com")
        
        assert "test@example.com" in emails
```

## Performance & Scalability

### Performance Optimizations

1. **Connection Pooling**: Reuse HTTP connections
2. **Concurrent Processing**: Process multiple domains simultaneously
3. **Caching**: Multi-layer caching reduces redundant requests
4. **Rate Limiting**: Prevents overwhelming target servers
5. **Async I/O**: Non-blocking operations for maximum throughput

### Scalability Considerations

1. **Horizontal Scaling**: API can run multiple instances behind load balancer
2. **Database Ready**: Job manager designed for easy database integration
3. **Stateless Design**: API endpoints are stateless for easy scaling
4. **Resource Management**: Proper cleanup prevents memory leaks

## Security Architecture

### API Security

```python
# Authentication
- API key-based authentication
- Configurable key validation
- Request rate limiting per key

# Input Validation
- Pydantic models for request validation
- SQL injection prevention
- XSS protection for outputs

# Security Headers
- CORS configuration
- Security middleware
- Request sanitization
```

### Data Security

```python
# Sensitive Data Handling
- No storage of scraped content by default
- Configurable data retention policies
- Secure logging (no sensitive data in logs)

# Network Security
- HTTPS support for production
- Respect for robots.txt
- Reasonable rate limiting
```

## Future Architecture Considerations

### Planned Enhancements (Sprint 3+)

1. **Playwright Integration**: JavaScript content rendering
2. **Database Integration**: PostgreSQL for persistent storage
3. **Message Queues**: Redis/RabbitMQ for job processing
4. **Monitoring**: Prometheus metrics and health checks
5. **Multi-tenancy**: Per-tenant isolation and quotas

### Migration Path

```python
# Current: In-memory job storage
job_manager = InMemoryJobManager()

# Future: Database-backed storage
job_manager = DatabaseJobManager(
    connection=postgresql_pool,
    queue=redis_queue
)
```

## Deployment Architecture

### Development Environment

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SCRAPER_DEBUG=true
      - SCRAPER_API_HOST=0.0.0.0
      - SCRAPER_API_PORT=8000
```

### Production Considerations

```python
# Production Settings
- Use environment variables for all configuration
- Enable comprehensive logging
- Configure rate limiting appropriately
- Set up health checks for load balancers
- Use connection pooling for databases
- Enable CORS for web client integration
```

This architecture provides a solid foundation for both current capabilities and future enhancements, ensuring scalability, maintainability, and production readiness.