# Async_Scraper Examples

This directory contains comprehensive examples demonstrating various use cases and integration patterns for the Async_Scraper platform.

## Table of Contents

### Basic Usage
- [python_client.py](python_client.py) - Complete Python client implementation
- [javascript_client.js](javascript_client.js) - Node.js/browser JavaScript client
- [curl_examples.sh](curl_examples.sh) - Command-line examples using curl

### Advanced Features
- [javascript_scraping.py](javascript_scraping.py) - JavaScript-enabled scraping with Playwright
- [proxy_management.py](proxy_management.py) - Comprehensive proxy management
- [multi_tenant_admin.py](multi_tenant_admin.py) - Admin interface for multi-tenancy

### Integration Examples  
- [django_integration.py](django_integration.py) - Django web application integration
- [fastapi_integration.py](fastapi_integration.py) - FastAPI service integration
- [celery_integration.py](celery_integration.py) - Background task processing with Celery
- [webhook_handler.py](webhook_handler.py) - WebSocket real-time updates handler

### Monitoring & Operations
- [prometheus_monitoring.py](prometheus_monitoring.py) - Custom metrics and monitoring
- [health_check_script.sh](health_check_script.sh) - Automated health checking
- [backup_restore.py](backup_restore.py) - Database backup and restore operations

### Production Examples
- [docker_compose_example](docker_compose_example/) - Complete production Docker setup
- [kubernetes_deployment](kubernetes_deployment/) - Kubernetes deployment manifests
- [terraform_infrastructure](terraform_infrastructure/) - Infrastructure as Code examples

## Getting Started

1. Install dependencies:
   ```bash
   pip install async-scraper aiohttp asyncio
   ```

2. Set up your environment:
   ```bash
   export ASYNC_SCRAPER_API_KEY="your-tenant-api-key"
   export ASYNC_SCRAPER_BASE_URL="https://api.yourdomain.com"
   ```

3. Run any example:
   ```bash
   python python_client.py
   ```

## Usage Examples

Each example includes:
- Complete working code
- Error handling patterns
- Configuration options
- Performance optimizations
- Multi-tenant considerations

Browse the individual files for detailed implementations and documentation.