# Async_Scraper

High-performance, async-first web scraping framework that transforms company names or domains into validated email leads. Available as both CLI tools and a comprehensive REST API platform with real-time job management.

## 🚀 Key Features

### Core Scraping Capabilities
- **Async-first architecture** using Python 3.11+ asyncio
- **Multi-layer caching** (L1/L2/L3) for performance optimization
- **Adaptive rate limiting** to respect server limits
- **Email extraction & validation** from web content
- **Domain crawling** with configurable depth

### REST API Platform
- **FastAPI server** with OpenAPI documentation
- **Background job processing** with progress tracking
- **Real-time WebSocket updates** for live monitoring
- **API key authentication** with rate limiting
- **Job management system** (create, monitor, cancel, delete)

### Production Ready
- **Modular design** with clean separation of concerns
- **Configuration management** with Pydantic validation
- **Structured logging** with contextual information
- **Comprehensive testing** with pytest
- **Type safety** with full type annotations

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
# Start the API server
async-scraper api --host 0.0.0.0 --port 8000

# Access API documentation
# http://localhost:8000/docs
```

### API Usage Examples

```bash
# Create a company scraping job
curl -X POST "http://localhost:8000/api/v1/scrape/companies" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"companies": ["Google", "Microsoft"], "max_emails_per_company": 5}'

# Response: {"job_id": "abc-123", "status": "pending"}

# Monitor job progress
curl -H "X-API-Key: your-api-key-here" \
  "http://localhost:8000/api/v1/jobs/abc-123"

# Get results when complete
curl -H "X-API-Key: your-api-key-here" \
  "http://localhost:8000/api/v1/jobs/abc-123/results"
```

### WebSocket Real-time Updates

```javascript
// Connect with authentication
const ws = new WebSocket('ws://localhost:8000/api/v1/ws?api_key=your-key');

// Subscribe to job updates
ws.send(JSON.stringify({
    action: 'subscribe',
    job_id: 'your-job-id'
}));

// Receive real-time progress updates
ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    console.log(`Progress: ${update.job.progress.percent}%`);
};
```

## 📚 Documentation

- **[Architecture Guide](ARCHITECTURE.md)** - Comprehensive system architecture
- **[Usage Guide](USAGE_GUIDE.md)** - Detailed CLI and API usage examples
- **[API Documentation](http://localhost:8000/docs)** - Interactive OpenAPI docs (when server is running)
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
│                     Core Services Layer                        │
│                                                                 │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ Scraper     │ │ Email       │ │ Web Client  │ │ Job         │ │
│ │ Manager     │ │ Extractor   │ │ Service     │ │ Manager     │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

The framework follows a modular architecture:

```
scraper/
├── api/           # REST API implementation (FastAPI, WebSocket, job management)
├── cli/           # Command-line interface
├── core/          # Core functionality (config, logging, utils)
├── data/          # Data loading, saving, and cleaning
└── services/      # Web scraping services and clients
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
    "l2_enabled": false,
    "l2_redis_url": "redis://localhost:6379"
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
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "api_keys": ["your-secret-key-here"],
    "rate_limit_per_minute": 100
  }
}
```

### Environment Variables

```bash
# API Configuration
export SCRAPER_API_HOST=0.0.0.0
export SCRAPER_API_PORT=8080
export SCRAPER_API_API_KEYS="key1,key2,key3"

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
- `GET /health/detailed` - Detailed system health

### Job Management
- `POST /api/v1/scrape/companies` - Create company scraping job
- `POST /api/v1/scrape/domains` - Create domain scraping job  
- `GET /api/v1/jobs` - List all jobs
- `GET /api/v1/jobs/{job_id}` - Get job status and details
- `GET /api/v1/jobs/{job_id}/results` - Get job results
- `POST /api/v1/jobs/{job_id}/cancel` - Cancel running job
- `DELETE /api/v1/jobs/{job_id}` - Delete completed job

### Real-time Updates
- `WS /api/v1/ws` - WebSocket endpoint for live job progress

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

- **Connection Pooling**: Efficient HTTP client reuse
- **Multi-layer Caching**: L1 (memory), L2 (Redis), L3 (disk)
- **Concurrent Processing**: Process multiple domains simultaneously
- **Rate Limiting**: Adaptive rate limiting to prevent overwhelming servers
- **Background Jobs**: Non-blocking API responses with background processing
- **Resource Management**: Proper cleanup and memory management

## 🔐 Security

- **API Key Authentication**: Secure access to protected endpoints
- **Rate Limiting**: Per-key rate limiting to prevent abuse
- **Input Validation**: Pydantic models for request validation
- **CORS Support**: Configurable CORS for web client integration
- **Secure Headers**: Security middleware for production deployment

## 🌟 Use Cases

### For Developers
- **Lead Generation**: Extract contact emails from company websites
- **Market Research**: Gather contact information from domain lists
- **Data Integration**: API integration into existing applications
- **Real-time Monitoring**: WebSocket updates for live dashboards

### For Businesses
- **Sales Automation**: Automated lead discovery and enrichment
- **Marketing Campaigns**: Contact list building and validation
- **Competitive Analysis**: Monitor competitor contact information
- **CRM Integration**: Direct integration with customer management systems

## 📋 Project Status

### Current Release: Phase 2 - API Platform
- ✅ **Sprint 1**: API Foundation - FastAPI server with authentication
- ✅ **Sprint 2**: Core API Endpoints - Job management and WebSocket support
- 🔄 **Sprint 3**: JavaScript Support - Playwright integration (next)

### Upcoming Features
- **JavaScript Content**: Playwright browser automation for dynamic content
- **Proxy Support**: Comprehensive proxy rotation and management
- **Database Integration**: PostgreSQL for persistent job storage
- **Multi-tenancy**: Per-tenant isolation and resource management
- **Advanced Monitoring**: Prometheus metrics and distributed tracing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with tests
4. Run the test suite: `pytest tests/`
5. Format code: `black scraper/ tests/`
6. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🔗 Links

- **GitHub Repository**: https://github.com/Jul352mf/Async_Scraper
- **API Documentation**: http://localhost:8000/docs (when server is running)
- **Issue Tracker**: https://github.com/Jul352mf/Async_Scraper/issues

---

*Built with ❤️ using Python, FastAPI, and asyncio for maximum performance and scalability.*
