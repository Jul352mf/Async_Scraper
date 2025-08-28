# Async_Scraper

High-performance, async-first web scraping framework that transforms company names or domains into validated email leads. Available as both CLI tools and a comprehensive REST API platform with enterprise-grade features including JavaScript support, proxy management, database persistence, multi-tenancy, and production monitoring.

## 🚀 Key Features

### Core Scraping Capabilities
- **Async-first architecture** using Python 3.11+ asyncio
- **Multi-layer caching** (L1/L2/L3) with Redis support for performance optimization
- **Intelligent proxy rotation** with health monitoring and multiple strategies
- **Email extraction & validation** from both static and dynamic content
- **Domain crawling** with configurable depth and JavaScript rendering

### Advanced JavaScript Support (Sprint 3)
- **Playwright integration** with Chromium, Firefox, and WebKit browsers
- **Dynamic content scraping** from single-page applications (SPAs)
- **Screenshot capture** with full-page and element-specific options
- **PDF generation** for documentation and archival
- **Browser pool management** with automatic resource cleanup

### Comprehensive Proxy Infrastructure (Sprint 4)
- **5 rotation strategies**: Round-robin, random, least-used, fastest, geographic
- **Health monitoring** with automated blacklisting and recovery
- **Proxy validation** and performance tracking
- **Geographic targeting** for region-specific content
- **HTTP & browser proxy** seamless integration

### Enterprise Database & Queue System (Sprint 5)
- **Multi-database support**: PostgreSQL for production, SQLite for development
- **Redis job queue** with priority scheduling, dependencies, and retry logic
- **Automated migrations** with version tracking and rollback capabilities
- **Persistent job storage** with comprehensive lifecycle management
- **Worker health monitoring** and distributed processing

### Production Monitoring & Multi-tenancy (Sprint 6)
- **Prometheus metrics** with 20+ operational metrics and tenant isolation
- **Health checking** for dependencies, system resources, and external connectivity
- **Multi-tenant architecture** with FREE/BASIC/PROFESSIONAL/ENTERPRISE plans
- **Admin interface** with 15+ management endpoints for operations
- **Distributed tracing** with OpenTelemetry integration

### REST API Platform
- **FastAPI server** with comprehensive OpenAPI documentation
- **Background job processing** with persistent storage and progress tracking
- **Real-time WebSocket updates** for live monitoring with tenant awareness
- **API key authentication** with tenant-specific rate limiting
- **Job management system** with database persistence (create, monitor, cancel, delete)

### Production Ready
- **Modular design** with clean separation of concerns and tenant isolation
- **Configuration management** with Pydantic validation and environment support
- **Structured logging** with contextual information and tenant tracking
- **Comprehensive testing** with 155+ tests covering all features
- **Type safety** with full type annotations throughout

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/Jul352mf/Async_Scraper.git
cd Async_Scraper

# Install in development mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

## 🛠 Quick Start

### CLI Usage

```bash
# Test configuration
async-scraper test-config

# Show version
async-scraper version

# Export default configuration
async-scraper export-config --output config.json

# Scrape emails from CSV file
async-scraper scrape companies.csv --output results.csv --format csv
```

### REST API Server

```bash
# Start the API server with multi-tenant support
async-scraper api --host 0.0.0.0 --port 8000

# Access API documentation
# http://localhost:8000/docs

# Admin interface for tenant management
# http://localhost:8000/admin/docs
```

### API Usage Examples

#### Traditional Scraping
```bash
# Create a company scraping job
curl -X POST "http://localhost:8000/api/v1/scrape/companies" \
  -H "X-API-Key: your-tenant-api-key" \
  -H "Content-Type: application/json" \
  -d '{"companies": ["Google", "Microsoft"], "max_emails_per_company": 5}'

# Response: {"job_id": "abc-123", "status": "pending"}
```

#### JavaScript-Enabled Scraping
```bash
# Create a JavaScript scraping job with Playwright
curl -X POST "http://localhost:8000/api/v1/enhanced/scrape/companies/js" \
  -H "X-API-Key: your-tenant-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "companies": ["OpenAI", "Stripe"], 
    "max_emails_per_company": 10,
    "config": {
      "take_screenshots": true,
      "browser_type": "chromium",
      "use_proxies": true,
      "proxy_strategy": "fastest"
    }
  }'
```

#### Proxy Management
```bash
# Add a new proxy
curl -X POST "http://localhost:8000/api/v1/proxy/proxies" \
  -H "X-API-Key: your-tenant-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://proxy.example.com:8080",
    "username": "user",
    "password": "pass",
    "country_code": "US"
  }'

# Check proxy health
curl -X POST "http://localhost:8000/api/v1/proxy/proxies/{proxy_id}/health-check" \
  -H "X-API-Key: your-tenant-api-key"
```

#### Visual Capture
```bash
# Take screenshots
curl -X POST "http://localhost:8000/api/v1/enhanced/capture/screenshot" \
  -H "X-API-Key: your-tenant-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com"],
    "full_page": true,
    "format": "png"
  }'

# Generate PDFs
curl -X POST "http://localhost:8000/api/v1/enhanced/capture/pdf" \
  -H "X-API-Key: your-tenant-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com"],
    "format": "A4",
    "margin": {"top": "1cm", "bottom": "1cm"}
  }'
```

#### Monitor job progress
```bash
curl -H "X-API-Key: your-tenant-api-key" \
  "http://localhost:8000/api/v1/jobs/abc-123"

# Get results when complete
curl -H "X-API-Key: your-tenant-api-key" \
  "http://localhost:8000/api/v1/jobs/abc-123/results"
```

### WebSocket Real-time Updates

```javascript
// Connect with tenant-specific authentication
const ws = new WebSocket('ws://localhost:8000/api/v1/ws?api_key=your-tenant-key');

// Subscribe to job updates
ws.send(JSON.stringify({
    action: 'subscribe',
    job_id: 'your-job-id'
}));

// Receive real-time progress updates with tenant isolation
ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    console.log(`Progress: ${update.job.progress.percent}%`);
    console.log(`Current item: ${update.job.progress.current_item}`);
};
```

### Multi-Tenant Admin Operations

```bash
# Create a new tenant (admin API key required)
curl -X POST "http://localhost:8000/admin/tenants/" \
  -H "X-API-Key: admin-super-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "contact_email": "admin@acme.com",
    "plan": "professional"
  }'

# Monitor system health
curl -H "X-API-Key: admin-super-key" \
  "http://localhost:8000/admin/monitoring/health"

# Get Prometheus metrics
curl -H "X-API-Key: admin-super-key" \
  "http://localhost:8000/admin/monitoring/metrics"
```

## 📚 Documentation

- **[Architecture Guide](ARCHITECTURE.md)** - Comprehensive system architecture with all Phase 2 features
- **[Usage Guide](USAGE_GUIDE.md)** - Detailed CLI and API usage examples with advanced features
- **[API Reference](API_REFERENCE.md)** - Complete API endpoint documentation with examples
- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment instructions and best practices
- **[API Documentation](http://localhost:8000/docs)** - Interactive OpenAPI docs (when server is running)
- **[Admin Documentation](http://localhost:8000/admin/docs)** - Multi-tenant admin interface documentation  
- **[Project Roadmap](ROADMAP.md)** - Development roadmap and sprint planning

## 🏗 Architecture

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
│                     Enhanced Services Layer                    │
│                                                                 │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ JavaScript  │ │ Proxy       │ │ Database    │ │ Multi-tenant│ │
│ │ Browser     │ │ Management  │ │ & Queue     │ │ Management  │ │
│ │ Engine      │ │ System      │ │ System      │ │ & Isolation │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
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
│ │ Multi-layer │ │ Rate        │ │ Config      │ │ Monitoring  │ │
│ │ Caching     │ │ Limiting    │ │ Management  │ │ & Metrics   │ │
│ │ (L1/L2/L3)  │ │ & Proxy     │ │ & Tenant    │ │ (Prometheus)│ │
│ │             │ │ Rotation    │ │ Isolation   │ │             │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

The framework follows a modular, multi-tenant architecture with enterprise features:

```
scraper/
├── api/                    # REST API implementation with tenant awareness
│   ├── routes/
│   │   ├── enhanced.py     # JavaScript & visual capture endpoints
│   │   ├── proxy.py        # Proxy management endpoints  
│   │   └── admin/          # Multi-tenant admin interface
│   ├── middleware/         # Authentication, rate limiting, tenant middleware
│   └── models/             # Pydantic models with tenant support
├── cli/                    # Command-line interface
├── core/                   # Core infrastructure with enterprise features
│   ├── config.py           # Multi-environment configuration
│   ├── monitoring/         # Prometheus metrics & health checks
│   ├── tenant/             # Multi-tenancy support & isolation
│   └── proxy/              # Comprehensive proxy management
├── services/               # Enhanced business logic
│   ├── browser_manager.py  # Playwright browser pool management
│   ├── js_scraper.py       # JavaScript content scraping
│   └── capture.py          # Screenshot & PDF generation
├── database/               # Enterprise persistence layer
│   ├── connection.py       # Multi-database connection management
│   ├── models.py           # Database models with tenant isolation
│   └── migrations.py       # Automated schema migrations
└── queue/                  # Distributed job processing
    ├── redis_queue.py      # Redis-based job queue
    └── worker.py           # Background job workers
```

## ⚙️ Configuration

### Configuration Hierarchy

1. **Environment Variables** (highest priority)
2. **Configuration Files** (.env, config.json)
3. **Default Values** (lowest priority)

### Example Configuration

```json
{
  "debug": false,
  "cache": {
    "l1_enabled": true,
    "l1_max_size": 1000,
    "l2_enabled": true,
    "l2_redis_url": "redis://localhost:6379",
    "l3_enabled": true,
    "l3_directory": "./cache"
  },
  "concurrency": {
    "max_concurrent_domains": 10,
    "max_concurrent_per_domain": 5,
    "global_rate_limit": 2.0
  },
  "scraping": {
    "timeout": 30.0,
    "max_crawl_depth": 3,
    "respect_robots_txt": true
  },
  "browser": {
    "max_browsers": 3,
    "max_contexts_per_browser": 10,
    "browser_type": "chromium",
    "headless": true,
    "timeout": 60.0
  },
  "proxy": {
    "enabled": true,
    "rotation_strategy": "round_robin",
    "health_check_interval": 300,
    "max_failures": 3
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "api_keys": ["your-secret-key-here"],
    "rate_limit_per_minute": 100
  },
  "database": {
    "use_sqlite": false,
    "host": "localhost",
    "port": 5432,
    "database": "async_scraper",
    "auto_migrate": true
  },
  "queue": {
    "use_redis": true,
    "redis_url": "redis://localhost:6379/1",
    "max_workers": 5,
    "max_retries": 3
  },
  "monitoring": {
    "prometheus_enabled": true,
    "health_check_interval": 30,
    "tracing_enabled": true
  },
  "multi_tenancy": {
    "enabled": true,
    "default_plan": "basic",
    "enforce_quotas": true
  }
}
```

### Environment Variables

```bash
# API Configuration
export SCRAPER_API_HOST=0.0.0.0
export SCRAPER_API_PORT=8080
export SCRAPER_API_API_KEYS="key1,key2,key3"

# Multi-Tenancy & Admin
export SCRAPER_MULTI_TENANCY_ENABLED=true
export SCRAPER_ADMIN_API_KEYS="admin-super-key"

# Database Configuration
export SCRAPER_DATABASE_USE_SQLITE=false
export SCRAPER_DATABASE_HOST=postgres.example.com
export SCRAPER_DATABASE_PORT=5432

# Queue Configuration
export SCRAPER_QUEUE_USE_REDIS=true
export SCRAPER_QUEUE_REDIS_URL="redis://redis.example.com:6379/1"
export SCRAPER_QUEUE_MAX_WORKERS=10

# Browser Configuration
export SCRAPER_BROWSER_MAX_BROWSERS=5
export SCRAPER_BROWSER_TYPE=chromium
export SCRAPER_BROWSER_HEADLESS=true

# Proxy Configuration
export SCRAPER_PROXY_ENABLED=true
export SCRAPER_PROXY_ROTATION_STRATEGY=fastest
export SCRAPER_PROXY_HEALTH_CHECK_INTERVAL=300

# Monitoring & Metrics
export SCRAPER_MONITORING_PROMETHEUS_ENABLED=true
export SCRAPER_MONITORING_TRACING_ENABLED=true
export SCRAPER_MONITORING_HEALTH_CHECK_INTERVAL=30

# Scraping Behavior
export SCRAPER_SCRAPING_TIMEOUT=45
export SCRAPER_CONCURRENCY_MAX_CONCURRENT_DOMAINS=15

# Caching
export SCRAPER_CACHE_L2_ENABLED=true
export SCRAPER_CACHE_L2_REDIS_URL="redis://localhost:6379"
```

## 🔌 API Endpoints

### Health & Status
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed system health with dependencies

### Traditional Job Management
- `POST /api/v1/scrape/companies` - Create company scraping job
- `POST /api/v1/scrape/domains` - Create domain scraping job  
- `GET /api/v1/jobs` - List all jobs with filtering
- `GET /api/v1/jobs/{job_id}` - Get job status and details
- `GET /api/v1/jobs/{job_id}/results` - Get job results
- `POST /api/v1/jobs/{job_id}/cancel` - Cancel running job
- `DELETE /api/v1/jobs/{job_id}` - Delete completed job

### Enhanced JavaScript Features
- `POST /api/v1/enhanced/scrape/companies/js` - JavaScript-enabled company scraping
- `POST /api/v1/enhanced/scrape/domains/js` - JavaScript-enabled domain crawling
- `POST /api/v1/enhanced/capture/screenshot` - Full-page screenshot capture
- `POST /api/v1/enhanced/capture/pdf` - PDF generation from web pages

### Comprehensive Proxy Management
- `GET /api/v1/proxy/proxies` - List all proxies with filtering
- `POST /api/v1/proxy/proxies` - Create new proxy configuration
- `GET /api/v1/proxy/proxies/{proxy_id}` - Get proxy details
- `PUT /api/v1/proxy/proxies/{proxy_id}` - Update proxy configuration
- `DELETE /api/v1/proxy/proxies/{proxy_id}` - Remove proxy
- `POST /api/v1/proxy/proxies/{proxy_id}/health-check` - Manual health check
- `GET /api/v1/proxy/stats` - Proxy system statistics

### Multi-Tenant Admin Interface
- `GET /admin/tenants/` - List all tenants
- `POST /admin/tenants/` - Create new tenant
- `GET /admin/tenants/{tenant_id}` - Get tenant details
- `PUT /admin/tenants/{tenant_id}` - Update tenant configuration
- `DELETE /admin/tenants/{tenant_id}` - Remove tenant
- `POST /admin/tenants/{tenant_id}/quota` - Update tenant quotas
- `GET /admin/tenants/{tenant_id}/usage` - Get tenant usage statistics

### Monitoring & System Management  
- `GET /admin/monitoring/health` - Comprehensive system health
- `GET /admin/monitoring/metrics` - Prometheus metrics endpoint
- `GET /admin/monitoring/stats` - Real-time system statistics
- `POST /admin/monitoring/gc` - Trigger garbage collection
- `POST /admin/monitoring/cache-clear` - Clear system caches

### Real-time Updates
- `WS /api/v1/ws` - WebSocket endpoint for live job progress with tenant isolation

## 🧪 Development

### Testing

```bash
# Run tests
pytest tests/

# Run tests with coverage
pytest tests/ --cov=scraper

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
```

### Code Quality

```bash
# Format code
black scraper/ tests/

# Lint code
ruff scraper/ tests/

# Type checking
mypy scraper/
```

### Development Server

```bash
# Start API server in development mode
SCRAPER_DEBUG=true async-scraper api

# Enable auto-reload for development
uvicorn scraper.api.main:app --reload --host 0.0.0.0 --port 8000
```

## 📈 Performance Features

- **Connection Pooling**: Efficient HTTP client reuse with browser connection management
- **Multi-layer Caching**: L1 (memory), L2 (Redis), L3 (disk) with tenant isolation
- **Concurrent Processing**: Process multiple domains simultaneously with browser pools
- **Intelligent Proxy Rotation**: 5 rotation strategies with health monitoring and geographic targeting
- **Background Jobs**: Non-blocking API responses with persistent Redis queue processing
- **Resource Management**: Proper cleanup of browsers, connections, and memory with tenant quotas
- **Database Connection Pooling**: Efficient PostgreSQL/SQLite connections with migration support
- **Prometheus Metrics**: 20+ performance metrics with tenant-specific monitoring
- **Distributed Processing**: Redis-based job queue with priority scheduling and worker management

## 🔐 Security

- **Multi-Tenant Authentication**: Tenant-specific API key authentication with plan-based access control
- **Rate Limiting**: Per-tenant rate limiting with hourly/daily/monthly quotas and burst handling
- **Input Validation**: Comprehensive Pydantic models for all request validation with tenant context
- **Data Isolation**: Complete tenant data separation at database and application levels
- **Secure Proxy Management**: Encrypted proxy credentials storage and validation
- **CORS Support**: Configurable CORS with tenant-specific origins
- **Security Headers**: Production security middleware with tenant-aware configurations
- **Browser Security**: Sandboxed browser contexts with resource isolation per tenant

## 🌟 Use Cases

### For SaaS Platforms
- **Multi-Tenant Lead Generation**: Complete tenant isolation with subscription plans and usage tracking
- **Enterprise API Integration**: Database-backed persistence with comprehensive monitoring and admin interface
- **Real-time Dashboard Applications**: WebSocket updates with tenant-specific job progress and metrics
- **Global Scraping Operations**: Intelligent proxy rotation with geographic targeting and health monitoring

### For Developers
- **JavaScript-Heavy Sites**: Dynamic content extraction with Playwright browser automation
- **Visual Documentation**: Screenshot and PDF capture with batch processing capabilities
- **Market Research**: Comprehensive domain crawling with database persistence and queue management
- **Performance Monitoring**: Prometheus metrics integration with distributed tracing and health checks

### For Businesses
- **Sales Automation**: Automated lead discovery with persistent storage and multi-tenant user management
- **Marketing Campaigns**: Contact list building with proxy rotation and JavaScript content support
- **Competitive Intelligence**: Monitor competitor websites with screenshot capture and change tracking
- **Enterprise Integration**: Complete API platform with admin interface, tenant management, and operational monitoring

## 📋 Project Status

### Phase 2 Complete - Enterprise SaaS Platform
- ✅ **Sprint 1**: API Foundation - FastAPI server with authentication
- ✅ **Sprint 2**: Core API Endpoints - Job management and WebSocket support  
- ✅ **Sprint 3**: JavaScript Support - Playwright integration with browser management
- ✅ **Sprint 4**: Proxy Support System - Comprehensive proxy infrastructure with health monitoring
- ✅ **Sprint 5**: Database & Job Queue Integration - Redis queue with PostgreSQL persistence
- ✅ **Sprint 6**: Monitoring & Multi-tenancy - Complete enterprise infrastructure with admin interface

### Phase 2 Features Delivered
- **Advanced JavaScript Scraping**: Playwright integration with multi-browser support and visual capture
- **Enterprise Proxy Management**: 5 rotation strategies with health monitoring and geographic targeting
- **Database Persistence**: PostgreSQL/SQLite with automated migrations and connection pooling  
- **Distributed Job Processing**: Redis-based queue with priority scheduling, dependencies, and retries
- **Multi-Tenant Architecture**: Complete tenant isolation with subscription plans and usage tracking
- **Production Monitoring**: Prometheus metrics, health checks, and distributed tracing
- **Admin Interface**: 15+ management endpoints for operations and tenant lifecycle management

### Ready for Phase 3
- **Plugin Architecture**: Extensible plugin system for custom scraping modules
- **Enhanced Security**: OAuth2 integration, audit logging, and advanced security features
- **Global Scaling**: Multi-region deployment with load balancing and data replication

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with comprehensive tests
4. Run the full test suite: `pytest tests/ --cov=scraper`
5. Format code: `black scraper/ tests/`
6. Lint code: `ruff scraper/ tests/`
7. Type check: `mypy scraper/`
8. Test API endpoints with tenant isolation
9. Submit a pull request with clear description

## 📄 License

MIT License - see LICENSE file for details.

## 🔗 Links

- **GitHub Repository**: https://github.com/Jul352mf/Async_Scraper
- **API Documentation**: http://localhost:8000/docs (when server is running)
- **Issue Tracker**: https://github.com/Jul352mf/Async_Scraper/issues

---

*Built with ❤️ using Python, FastAPI, and asyncio for maximum performance and scalability.*
