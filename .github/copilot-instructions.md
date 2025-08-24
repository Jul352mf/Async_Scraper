# GitHub Copilot Instructions

## Repository Context
This repository contains **Async_Scraper**, a production-ready async web scraping framework with both CLI tools and a comprehensive REST API platform. The codebase combines high-performance scraping capabilities with enterprise-grade job management, real-time WebSocket updates, and scalable architecture.

## Architecture Overview
The system is built with a modular, async-first architecture:
- **CLI Interface**: Command-line tools for direct scraping operations
- **REST API Server**: FastAPI-based server with job management and WebSocket support  
- **Core Services**: Scraping, email extraction, and web client services
- **Infrastructure**: Multi-layer caching, rate limiting, configuration management
- **Job Management**: Background processing with progress tracking and real-time updates

## Key Development Guidelines

### Code Quality Standards
- **Type hints are mandatory** - All functions must have proper type annotations
- **Async-first approach** - Use async/await for all I/O operations
- **Error handling** - Always handle potential failures with proper logging
- **Resource cleanup** - Ensure proper cleanup of async resources (connections, files)
- **API-first design** - New features should consider both CLI and API interfaces

### Pull Request Guidelines
- **Run full test suite** before submitting: `pytest tests/ --cov=scraper`
- **Maintain coverage** - Keep test coverage above 25% (aim for higher)
- **Format code** - Use `black scraper/ tests/` before committing
- **Lint code** - Run `ruff scraper/ tests/` to catch issues
- **Type check** - Run `mypy scraper/` to ensure type safety
- **Test API endpoints** - Use `TestClient` for API integration tests

### Common Patterns to Follow

#### Async Function Signatures
```python
async def process_domain(
    domain: str,
    client: aiohttp.ClientSession,
    config: Config,
) -> Optional[List[str]]:
    """Process a single domain and extract emails."""
    # Implementation here
```

#### Error Handling with Context
```python
logger = get_logger(__name__)

try:
    result = await some_async_operation()
except aiohttp.ClientError as e:
    logger.error("HTTP request failed", domain=domain, error=str(e))
    return None
except Exception as e:
    logger.error("Unexpected error", operation="process_domain", error=str(e))
    raise
```

#### Configuration Access
```python
# Always use the global config or pass config explicitly
from scraper.core.config import get_config

config = get_config()
timeout = config.scraping.timeout
```

#### API Endpoint Pattern
```python
from fastapi import APIRouter, Depends, HTTPException
from scraper.api.middleware.auth import get_api_key
from scraper.api.models import ResponseModel

router = APIRouter(prefix="/api/v1", tags=["feature"])

@router.post("/endpoint", response_model=ResponseModel)
async def create_endpoint(
    request: RequestModel,
    api_key: str = Depends(get_api_key)
) -> ResponseModel:
    """Create a new resource with proper validation."""
    try:
        # Business logic here
        return ResponseModel(success=True, data=result)
    except Exception as e:
        logger.error("Endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
```

#### Job Management Pattern
```python
from scraper.api.job_manager import get_job_manager
from scraper.api.models import JobType, JobStatus

job_manager = get_job_manager()

# Create job
job = job_manager.create_job(
    job_type=JobType.SCRAPE_COMPANIES,
    config={"companies": companies, "max_emails_per_company": max_emails}
)

# Start background processing
await job_manager.start_job(job.id)

# Update progress (in background task)
job_manager.update_job_progress(
    job.id, 
    progress={"percent": 45.5, "current_item": "example.com"}
)
```

#### WebSocket Message Handling
```python
from fastapi import WebSocket
import json

async def handle_websocket_message(websocket: WebSocket, message: dict):
    """Handle incoming WebSocket messages."""
    action = message.get("action")
    
    if action == "subscribe":
        job_id = message.get("job_id")
        await websocket_manager.subscribe_to_job(websocket, job_id)
        await websocket.send_text(json.dumps({
            "type": "subscription_confirmed",
            "job_id": job_id
        }))
    elif action == "unsubscribe":
        job_id = message.get("job_id")
        await websocket_manager.unsubscribe_from_job(websocket, job_id)
```

### Testing Patterns

#### Async Test Structure
```python
import pytest
from aioresponses import aioresponses
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_email_extraction():
    with aioresponses() as mock:
        mock.get("https://example.com", payload={"content": "test@example.com"})
        # Test implementation
```

#### API Integration Tests
```python
from fastapi.testclient import TestClient
from scraper.api.main import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-api-key-123456"}

def test_create_scraping_job(client, auth_headers):
    response = client.post(
        "/api/v1/scrape/companies",
        json={"companies": ["Google"], "max_emails_per_company": 5},
        headers=auth_headers
    )
    assert response.status_code == 200
    assert "job_id" in response.json()
```

#### WebSocket Testing
```python
from fastapi.testclient import TestClient

def test_websocket_subscription(client):
    with client.websocket_connect("/api/v1/ws?api_key=test-key") as websocket:
        # Send subscription message
        websocket.send_json({"action": "subscribe", "job_id": "test-job-id"})
        
        # Receive confirmation
        data = websocket.receive_json()
        assert data["type"] == "subscription_confirmed"
```

#### Mock External Services
- Use `aioresponses` for HTTP mocking
- Mock Redis connections when Redis cache is involved  
- Use temporary files for file I/O testing
- Use `TestClient` for API endpoint testing
- Mock WebSocket connections for real-time feature testing

### File Organization Rules
- **Core functionality** goes in `scraper/core/`
- **Business logic** goes in `scraper/services/`  
- **Data processing** goes in `scraper/data/`
- **CLI commands** go in `scraper/cli/`
- **API implementation** goes in `scraper/api/`
  - `routes/` - API endpoint definitions
  - `models/` - Pydantic request/response models  
  - `middleware/` - Authentication, rate limiting, etc.
- **Tests mirror source structure** in `tests/unit/` and `tests/integration/`

### Performance Considerations
- Use connection pooling for HTTP requests
- Implement proper backpressure with semaphores
- Cache expensive operations appropriately
- Monitor memory usage with large datasets
- Use background job processing for long-running operations
- Implement WebSocket connection management efficiently
- Consider database connection pooling for persistent storage

### Security Guidelines  
- Never commit API keys or credentials
- Validate all external inputs using Pydantic models
- Use environment variables for configuration
- Sanitize data before processing
- Implement API key authentication for all protected endpoints
- Use CORS middleware appropriately for web clients
- Validate WebSocket authentication via query parameters

### API Development Standards
- **RESTful Design**: Follow REST principles for endpoint structure
- **Pydantic Models**: Use Pydantic for all request/response validation
- **Error Responses**: Return consistent error response format
- **Authentication**: Require API keys for all protected endpoints
- **Rate Limiting**: Implement per-key rate limiting
- **OpenAPI Docs**: Maintain comprehensive API documentation
- **Background Processing**: Use job manager for long-running tasks
- **Real-time Updates**: Implement WebSocket for progress updates

### Job Management Guidelines
- **UUID-based IDs**: Use UUIDs for all job identifiers
- **Status Lifecycle**: Manage proper job state transitions (pending → running → completed/failed/cancelled)
- **Progress Tracking**: Provide meaningful progress updates with estimates
- **Resource Cleanup**: Ensure proper cleanup of job resources
- **Error Handling**: Capture and report detailed error information
- **Result Storage**: Store job results with appropriate retention policies

## Git Workflow
- Create feature branches from `main`
- Use descriptive commit messages
- Squash commits before merging
- Update documentation when adding features
- Test both CLI and API functionality for changes
- Update API documentation for endpoint changes

## Documentation Standards
- Update docstrings for new public methods
- Include usage examples for complex functionality
- Update README.md for significant changes
- Update ARCHITECTURE.md for architectural changes
- Update USAGE_GUIDE.md for new features
- Maintain OpenAPI documentation for API endpoints
- Keep this instruction file updated for major architectural changes

## Current Sprint Status (Phase 2)
- ✅ **Sprint 1**: API Foundation - FastAPI server with authentication
- ✅ **Sprint 2**: Core API Endpoints - Job management and WebSocket support
- 🔄 **Sprint 3**: JavaScript Support - Playwright integration (in progress)
- ⏳ **Sprint 4**: Proxy Support System
- ⏳ **Sprint 5**: Database & Job Queue Integration
- ⏳ **Sprint 6**: Monitoring & Multi-tenancy

## Integration Points
- **CLI ↔ Services**: CLI commands use core services directly
- **API ↔ Services**: API endpoints orchestrate service calls via job manager
- **WebSocket ↔ Jobs**: Real-time updates broadcast job progress
- **Configuration**: Shared configuration system across CLI and API
- **Caching**: Multi-layer cache used by all components
- **Logging**: Structured logging throughout the system

Remember: This is an async-first framework with both CLI and API interfaces. When implementing new features, consider both use cases and maintain the modular architecture for scalability and maintainability.