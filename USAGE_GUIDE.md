# Async_Scraper Usage Guide

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation & Setup](#installation--setup)
3. [CLI Usage](#cli-usage)
4. [REST API Usage](#rest-api-usage)
5. [WebSocket Real-time Updates](#websocket-real-time-updates)
6. [Configuration Guide](#configuration-guide)
7. [Advanced Usage](#advanced-usage)
8. [Integration Examples](#integration-examples)
9. [Troubleshooting](#troubleshooting)

## Quick Start

### 30-Second Demo

```bash
# Install the package
pip install -e .

# Test your configuration
async-scraper test-config

# Scrape emails from companies (CLI)
async-scraper scrape companies.csv --output results.csv

# Or start the API server
async-scraper api --host 0.0.0.0 --port 8000
```

```bash
# Create a scraping job via API
curl -X POST "http://localhost:8000/api/v1/scrape/companies" \
  -H "X-API-Key: test-api-key-123456" \
  -H "Content-Type: application/json" \
  -d '{"companies": ["Google", "Microsoft"], "max_emails_per_company": 5}'

# Monitor job progress
curl -H "X-API-Key: test-api-key-123456" \
  "http://localhost:8000/api/v1/jobs/{job_id}"
```

## Installation & Setup

### Prerequisites

- Python 3.11 or higher
- Optional: Redis for advanced caching (L2 cache)
- Optional: PostgreSQL for persistent job storage (future releases)

### Installation Options

#### Development Installation

```bash
# Clone the repository
git clone https://github.com/Jul352mf/Async_Scraper.git
cd Async_Scraper

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Verify installation
async-scraper version
```

#### Production Installation

```bash
# Install from PyPI (when available)
pip install async-scraper

# Or from source
pip install git+https://github.com/Jul352mf/Async_Scraper.git
```

### Initial Configuration

```bash
# Export default configuration to file
async-scraper export-config --output config.json

# Test your configuration
async-scraper test-config

# Test with custom config file
async-scraper test-config --config config.json
```

## CLI Usage

### Basic Commands

```bash
# Show help
async-scraper --help

# Show version
async-scraper version

# Test configuration
async-scraper test-config
```

### Scraping Commands

#### Scrape Companies

```bash
# Basic usage - from CSV file
async-scraper scrape companies.csv

# With output file
async-scraper scrape companies.csv --output results.csv

# Specify output format (csv, json, xlsx)
async-scraper scrape companies.csv --format json --output results.json

# Limit emails per company
async-scraper scrape companies.csv --max-emails 10

# Use custom configuration
async-scraper scrape companies.csv --config my-config.json
```

#### CSV File Format

Create a CSV file with company names:

```csv
company
Google
Microsoft
OpenAI
GitHub
```

Or with additional metadata:

```csv
company,industry,priority
Google,Technology,high
Microsoft,Technology,high
Local Coffee Shop,Food & Beverage,low
```

### Configuration Commands

```bash
# Export current configuration
async-scraper export-config --output my-config.json

# Validate configuration file
async-scraper validate-config --config my-config.json

# Show current configuration
async-scraper show-config
```

### API Server Commands

```bash
# Start API server with defaults
async-scraper api

# Custom host and port
async-scraper api --host 0.0.0.0 --port 8080

# Enable debug mode
async-scraper api --debug

# Use custom configuration
async-scraper api --config production-config.json
```

## REST API Usage

### Authentication

All API endpoints (except basic health check) require authentication via API key:

```bash
# Set API key in header
curl -H "X-API-Key: your-secret-key" http://localhost:8000/api/v1/jobs
```

### Health Checks

```bash
# Basic health check (no auth required)
curl http://localhost:8000/health

# Response:
{
  "status": "healthy",
  "service": "async-scraper-api",
  "version": "0.1.0",
  "timestamp": "2024-01-20T10:30:00Z"
}

# Detailed health check (requires auth)
curl -H "X-API-Key: test-key" http://localhost:8000/health/detailed

# Response:
{
  "status": "healthy",
  "service": "async-scraper-api",
  "version": "0.1.0",
  "timestamp": "2024-01-20T10:30:00Z",
  "checks": {
    "cache": "healthy",
    "rate_limiter": "healthy"
  },
  "metrics": {
    "active_jobs": 0,
    "total_requests": 1247
  }
}
```

### Creating Scraping Jobs

#### Scrape Companies

```bash
# Create a company scraping job
curl -X POST "http://localhost:8000/api/v1/scrape/companies" \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "companies": ["Google", "Microsoft", "OpenAI"],
    "max_emails_per_company": 5,
    "config": {
      "scraping": {
        "timeout": 30,
        "max_crawl_depth": 2
      }
    }
  }'

# Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Created scraping job for 3 companies",
  "estimated_completion": "2024-01-20T10:35:00Z"
}
```

#### Scrape Domains

```bash
# Create a domain scraping job
curl -X POST "http://localhost:8000/api/v1/scrape/domains" \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "domains": ["example.com", "test.org"],
    "max_depth": 3,
    "max_emails_per_domain": 10,
    "config": {
      "scraping": {
        "respect_robots_txt": true,
        "timeout": 45
      }
    }
  }'

# Response:
{
  "job_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "pending",
  "message": "Created domain scraping job for 2 domains",
  "estimated_completion": "2024-01-20T10:40:00Z"
}
```

### Managing Jobs

#### List All Jobs

```bash
# Get all jobs
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/jobs"

# Filter by status
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/jobs?status=running"

# Pagination
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/jobs?skip=0&limit=10"

# Response:
{
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "scrape_companies",
      "status": "completed",
      "created_at": "2024-01-20T10:30:00Z",
      "completed_at": "2024-01-20T10:34:30Z",
      "progress": {
        "percent": 100.0,
        "total_items": 3,
        "completed_items": 3
      }
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 10
}
```

#### Get Job Details

```bash
# Get specific job status
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000"

# Response:
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "scrape_companies",
  "status": "running",
  "created_at": "2024-01-20T10:30:00Z",
  "started_at": "2024-01-20T10:30:15Z",
  "progress": {
    "percent": 66.7,
    "current_item": "Microsoft",
    "total_items": 3,
    "completed_items": 2,
    "estimated_completion": "2024-01-20T10:34:00Z"
  },
  "config": {
    "companies": ["Google", "Microsoft", "OpenAI"],
    "max_emails_per_company": 5
  }
}
```

#### Get Job Results

```bash
# Get results for completed job
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/results"

# Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "results": {
    "companies_processed": 3,
    "total_emails_found": 12,
    "emails_by_company": {
      "Google": [
        "careers@google.com",
        "support@google.com",
        "press@google.com"
      ],
      "Microsoft": [
        "careers@microsoft.com",
        "support@microsoft.com",
        "news@microsoft.com",
        "investors@microsoft.com"
      ],
      "OpenAI": [
        "hello@openai.com",
        "careers@openai.com",
        "support@openai.com",
        "safety@openai.com",
        "research@openai.com"
      ]
    }
  },
  "metadata": {
    "processing_time_seconds": 45.2,
    "domains_crawled": 8,
    "pages_processed": 23,
    "cache_hit_rate": 0.34
  }
}
```

#### Cancel Running Job

```bash
# Cancel a running job
curl -X POST -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/cancel"

# Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "message": "Job cancellation requested"
}
```

#### Delete Completed Job

```bash
# Delete a completed job
curl -X DELETE -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000"

# Response:
{
  "message": "Job deleted successfully"
}
```

## WebSocket Real-time Updates

### Connection Setup

```javascript
// Connect to WebSocket with API key authentication
const apiKey = 'your-secret-key';
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws?api_key=${apiKey}`);

ws.onopen = function(event) {
    console.log('Connected to Async Scraper WebSocket');
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    handleWebSocketMessage(data);
};

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};

ws.onclose = function(event) {
    console.log('WebSocket connection closed:', event.code, event.reason);
};
```

### Subscribing to Job Updates

```javascript
// Subscribe to updates for a specific job
function subscribeToJob(jobId) {
    const message = {
        action: 'subscribe',
        job_id: jobId
    };
    ws.send(JSON.stringify(message));
}

// Unsubscribe from job updates
function unsubscribeFromJob(jobId) {
    const message = {
        action: 'unsubscribe',
        job_id: jobId
    };
    ws.send(JSON.stringify(message));
}

// Handle incoming messages
function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'connection_ack':
            console.log('Connection acknowledged:', data.message);
            break;
            
        case 'job_update':
            updateJobProgress(data.job_id, data.job);
            break;
            
        case 'job_completed':
            handleJobCompletion(data.job_id, data.job);
            break;
            
        case 'error':
            console.error('WebSocket error:', data.message);
            break;
            
        default:
            console.log('Unknown message type:', data.type);
    }
}

// Update UI with job progress
function updateJobProgress(jobId, jobData) {
    const progressPercent = jobData.progress.percent;
    const currentItem = jobData.progress.current_item;
    
    console.log(`Job ${jobId}: ${progressPercent}% complete, processing ${currentItem}`);
    
    // Update progress bar
    document.getElementById(`job-${jobId}-progress`).style.width = `${progressPercent}%`;
    document.getElementById(`job-${jobId}-status`).textContent = 
        `Processing ${currentItem} (${jobData.progress.completed_items}/${jobData.progress.total_items})`;
}
```

### Complete WebSocket Example

```html
<!DOCTYPE html>
<html>
<head>
    <title>Async Scraper Monitor</title>
    <style>
        .job-card {
            border: 1px solid #ccc;
            margin: 10px;
            padding: 15px;
            border-radius: 5px;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #f0f0f0;
            border-radius: 10px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background-color: #4CAF50;
            transition: width 0.3s ease;
        }
    </style>
</head>
<body>
    <h1>Async Scraper Job Monitor</h1>
    
    <div id="connection-status">Disconnected</div>
    
    <button onclick="createTestJob()">Create Test Job</button>
    
    <div id="jobs-container"></div>

    <script>
        const apiKey = 'test-api-key-123456';
        const apiBase = 'http://localhost:8000/api/v1';
        const ws = new WebSocket(`ws://localhost:8000/api/v1/ws?api_key=${apiKey}`);
        
        const activeJobs = new Map();

        ws.onopen = function(event) {
            document.getElementById('connection-status').textContent = 'Connected';
            document.getElementById('connection-status').style.color = 'green';
        };

        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.type === 'job_update') {
                updateJobDisplay(data.job_id, data.job);
            } else if (data.type === 'job_completed') {
                markJobCompleted(data.job_id, data.job);
            }
        };

        ws.onclose = function(event) {
            document.getElementById('connection-status').textContent = 'Disconnected';
            document.getElementById('connection-status').style.color = 'red';
        };

        async function createTestJob() {
            try {
                const response = await fetch(`${apiBase}/scrape/companies`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': apiKey
                    },
                    body: JSON.stringify({
                        companies: ['Google', 'Microsoft', 'OpenAI'],
                        max_emails_per_company: 5
                    })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    addJobToDisplay(result.job_id, 'pending');
                    subscribeToJob(result.job_id);
                } else {
                    alert('Failed to create job: ' + result.error);
                }
            } catch (error) {
                alert('Error creating job: ' + error.message);
            }
        }

        function subscribeToJob(jobId) {
            ws.send(JSON.stringify({
                action: 'subscribe',
                job_id: jobId
            }));
        }

        function addJobToDisplay(jobId, status) {
            const container = document.getElementById('jobs-container');
            const jobCard = document.createElement('div');
            jobCard.className = 'job-card';
            jobCard.id = `job-${jobId}`;
            
            jobCard.innerHTML = `
                <h3>Job ${jobId}</h3>
                <p>Status: <span id="status-${jobId}">${status}</span></p>
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-${jobId}" style="width: 0%"></div>
                </div>
                <p id="details-${jobId}">Waiting to start...</p>
            `;
            
            container.appendChild(jobCard);
            activeJobs.set(jobId, { status, progress: 0 });
        }

        function updateJobDisplay(jobId, jobData) {
            const statusElement = document.getElementById(`status-${jobId}`);
            const progressElement = document.getElementById(`progress-${jobId}`);
            const detailsElement = document.getElementById(`details-${jobId}`);
            
            if (statusElement) {
                statusElement.textContent = jobData.status;
                progressElement.style.width = `${jobData.progress.percent}%`;
                detailsElement.textContent = 
                    `Processing ${jobData.progress.current_item} (${jobData.progress.completed_items}/${jobData.progress.total_items})`;
            }
        }

        function markJobCompleted(jobId, jobData) {
            const statusElement = document.getElementById(`status-${jobId}`);
            const detailsElement = document.getElementById(`details-${jobId}`);
            
            if (statusElement) {
                statusElement.textContent = jobData.status;
                statusElement.style.color = jobData.status === 'completed' ? 'green' : 'red';
                detailsElement.textContent = 
                    jobData.status === 'completed' 
                        ? `Completed successfully - ${jobData.progress.completed_items} items processed`
                        : `Job failed or was cancelled`;
            }
        }
    </script>
</body>
</html>
```

## Configuration Guide

### Configuration File Structure

```json
{
  "debug": false,
  "cache": {
    "l1_enabled": true,
    "l1_max_size": 1000,
    "l2_enabled": false,
    "l2_redis_url": "redis://localhost:6379",
    "l3_enabled": true,
    "l3_directory": "./cache"
  },
  "concurrency": {
    "max_concurrent_domains": 10,
    "max_concurrent_per_domain": 5,
    "global_rate_limit": 2.0,
    "respect_delays": true
  },
  "scraping": {
    "timeout": 30.0,
    "max_crawl_depth": 3,
    "respect_robots_txt": true,
    "max_emails_per_company": 50,
    "max_emails_per_domain": 100,
    "user_agent": "AsyncScraper/1.0"
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "api_keys": ["your-secret-key-here"],
    "rate_limit_per_minute": 100,
    "cors_origins": ["*"],
    "docs_enabled": true
  },
  "logging": {
    "level": "INFO",
    "format": "json",
    "file": null
  }
}
```

### Environment Variables

All configuration options can be set via environment variables with the `SCRAPER_` prefix:

```bash
# Basic configuration
export SCRAPER_DEBUG=true
export SCRAPER_API_HOST=0.0.0.0
export SCRAPER_API_PORT=8080

# API keys (comma-separated)
export SCRAPER_API_API_KEYS="key1,key2,key3"

# Concurrency settings
export SCRAPER_CONCURRENCY_MAX_CONCURRENT_DOMAINS=15
export SCRAPER_CONCURRENCY_GLOBAL_RATE_LIMIT=1.5

# Scraping behavior
export SCRAPER_SCRAPING_TIMEOUT=45
export SCRAPER_SCRAPING_MAX_CRAWL_DEPTH=2
export SCRAPER_SCRAPING_RESPECT_ROBOTS_TXT=false

# Caching
export SCRAPER_CACHE_L1_ENABLED=true
export SCRAPER_CACHE_L2_ENABLED=true
export SCRAPER_CACHE_L2_REDIS_URL="redis://localhost:6379"
```

### Configuration Best Practices

#### Development Configuration

```json
{
  "debug": true,
  "cache": {
    "l1_enabled": true,
    "l2_enabled": false,
    "l3_enabled": true
  },
  "concurrency": {
    "max_concurrent_domains": 3,
    "max_concurrent_per_domain": 2,
    "global_rate_limit": 1.0
  },
  "scraping": {
    "timeout": 20.0,
    "max_crawl_depth": 2,
    "max_emails_per_company": 10
  },
  "api": {
    "docs_enabled": true
  },
  "logging": {
    "level": "DEBUG"
  }
}
```

#### Production Configuration

```json
{
  "debug": false,
  "cache": {
    "l1_enabled": true,
    "l1_max_size": 5000,
    "l2_enabled": true,
    "l2_redis_url": "redis://redis-server:6379",
    "l3_enabled": true
  },
  "concurrency": {
    "max_concurrent_domains": 20,
    "max_concurrent_per_domain": 10,
    "global_rate_limit": 3.0
  },
  "scraping": {
    "timeout": 60.0,
    "max_crawl_depth": 4,
    "max_emails_per_company": 100,
    "respect_robots_txt": true
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "rate_limit_per_minute": 1000,
    "cors_origins": ["https://yourdomain.com"],
    "docs_enabled": false
  },
  "logging": {
    "level": "INFO",
    "format": "json",
    "file": "/var/log/async-scraper.log"
  }
}
```

## Advanced Usage

### Custom Request Configuration

You can override global configuration for individual API requests:

```bash
curl -X POST "http://localhost:8000/api/v1/scrape/companies" \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "companies": ["Google"],
    "max_emails_per_company": 5,
    "config": {
      "scraping": {
        "timeout": 60,
        "max_crawl_depth": 4,
        "respect_robots_txt": false
      },
      "concurrency": {
        "max_concurrent_per_domain": 10,
        "global_rate_limit": 0.5
      }
    }
  }'
```

### Batch Processing

For large-scale operations, process jobs in batches:

```python
import asyncio
import aiohttp
import json

async def create_batch_jobs(companies_list, api_key, batch_size=10):
    """Create multiple scraping jobs in batches."""
    async with aiohttp.ClientSession() as session:
        jobs = []
        
        for i in range(0, len(companies_list), batch_size):
            batch = companies_list[i:i+batch_size]
            
            payload = {
                "companies": batch,
                "max_emails_per_company": 10
            }
            
            headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
            
            async with session.post(
                "http://localhost:8000/api/v1/scrape/companies",
                json=payload,
                headers=headers
            ) as response:
                result = await response.json()
                jobs.append(result["job_id"])
                
            # Add delay between batches to respect rate limits
            await asyncio.sleep(1)
        
        return jobs

# Usage
companies = ["Google", "Microsoft", "Apple", "Amazon", "Meta"]
job_ids = await create_batch_jobs(companies, "your-api-key", batch_size=2)
```

### Monitoring Job Progress

```python
async def monitor_job_until_completion(job_id, api_key):
    """Monitor a job until it completes."""
    async with aiohttp.ClientSession() as session:
        headers = {"X-API-Key": api_key}
        
        while True:
            async with session.get(
                f"http://localhost:8000/api/v1/jobs/{job_id}",
                headers=headers
            ) as response:
                job_data = await response.json()
                
                status = job_data["status"]
                progress = job_data.get("progress", {})
                
                print(f"Job {job_id}: {status} - {progress.get('percent', 0):.1f}%")
                
                if status in ["completed", "failed", "cancelled"]:
                    return job_data
                    
                await asyncio.sleep(5)  # Check every 5 seconds
```

## Integration Examples

### Python Integration

```python
import asyncio
import aiohttp
from typing import List, Dict, Optional

class AsyncScraperClient:
    """Python client for Async Scraper API."""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"X-API-Key": self.api_key} if self.api_key else {}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def scrape_companies(
        self, 
        companies: List[str], 
        max_emails_per_company: int = 50,
        config: Optional[Dict] = None
    ) -> str:
        """Create a company scraping job."""
        payload = {
            "companies": companies,
            "max_emails_per_company": max_emails_per_company
        }
        if config:
            payload["config"] = config
        
        async with self.session.post(
            f"{self.base_url}/api/v1/scrape/companies",
            json=payload
        ) as response:
            result = await response.json()
            if response.status == 200:
                return result["job_id"]
            else:
                raise Exception(f"API error: {result}")
    
    async def get_job_status(self, job_id: str) -> Dict:
        """Get job status and progress."""
        async with self.session.get(
            f"{self.base_url}/api/v1/jobs/{job_id}"
        ) as response:
            return await response.json()
    
    async def get_job_results(self, job_id: str) -> Dict:
        """Get job results."""
        async with self.session.get(
            f"{self.base_url}/api/v1/jobs/{job_id}/results"
        ) as response:
            return await response.json()
    
    async def wait_for_completion(self, job_id: str, poll_interval: int = 5) -> Dict:
        """Wait for job to complete and return results."""
        while True:
            status_data = await self.get_job_status(job_id)
            status = status_data["status"]
            
            if status == "completed":
                return await self.get_job_results(job_id)
            elif status in ["failed", "cancelled"]:
                raise Exception(f"Job {job_id} {status}: {status_data}")
            
            await asyncio.sleep(poll_interval)

# Usage example
async def main():
    async with AsyncScraperClient(api_key="your-key") as client:
        # Create job
        job_id = await client.scrape_companies(
            companies=["Google", "Microsoft"],
            max_emails_per_company=10
        )
        
        print(f"Created job: {job_id}")
        
        # Wait for completion and get results
        results = await client.wait_for_completion(job_id)
        print(f"Found {len(results['results']['emails_by_company'])} companies")
        
        for company, emails in results["results"]["emails_by_company"].items():
            print(f"{company}: {len(emails)} emails")

if __name__ == "__main__":
    asyncio.run(main())
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');
const WebSocket = require('ws');

class AsyncScraperClient {
    constructor(baseUrl = 'http://localhost:8000', apiKey = null) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
        this.headers = apiKey ? { 'X-API-Key': apiKey } : {};
    }

    async scrapeCompanies(companies, maxEmailsPerCompany = 50, config = null) {smartt
        const payload = {
            companies,
            max_emails_per_company: maxEmailsPerCompany,
            ...(config && { config })
        };

        try {
            const response = await axios.post(
                `${this.baseUrl}/api/v1/scrape/companies`,
                payload,
                { headers: this.headers }
            );
            return response.data.job_id;
        } catch (error) {
            throw new Error(`API error: ${error.response?.data || error.message}`);
        }
    }

    async getJobStatus(jobId) {
        const response = await axios.get(
            `${this.baseUrl}/api/v1/jobs/${jobId}`,
            { headers: this.headers }
        );
        return response.data;
    }

    async getJobResults(jobId) {
        const response = await axios.get(
            `${this.baseUrl}/api/v1/jobs/${jobId}/results`,
            { headers: this.headers }
        );
        return response.data;
    }

    async waitForCompletion(jobId, pollInterval = 5000) {
        while (true) {
            const statusData = await this.getJobStatus(jobId);
            const status = statusData.status;

            if (status === 'completed') {
                return await this.getJobResults(jobId);
            } else if (['failed', 'cancelled'].includes(status)) {
                throw new Error(`Job ${jobId} ${status}`);
            }

            await new Promise(resolve => setTimeout(resolve, pollInterval));
        }
    }

    connectWebSocket() {
        const wsUrl = `ws://localhost:8000/api/v1/ws?api_key=${this.apiKey}`;
        const ws = new WebSocket(wsUrl);

        ws.on('open', () => {
            console.log('Connected to Async Scraper WebSocket');
        });

        ws.on('message', (data) => {
            const message = JSON.parse(data);
            this.handleWebSocketMessage(message);
        });

        return ws;
    }

    subscribeToJob(ws, jobId) {
        ws.send(JSON.stringify({
            action: 'subscribe',
            job_id: jobId
        }));
    }

    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'job_update':
                console.log(`Job ${message.job_id} progress: ${message.job.progress.percent}%`);
                break;
            case 'job_completed':
                console.log(`Job ${message.job_id} completed with status: ${message.job.status}`);
                break;
            default:
                console.log('Unknown message:', message);
        }
    }
}

// Usage
async function main() {
    const client = new AsyncScraperClient('http://localhost:8000', 'your-api-key');

    try {
        // Create job
        const jobId = await client.scrapeCompanies(['Google', 'Microsoft']);
        console.log(`Created job: ${jobId}`);

        // Set up WebSocket monitoring
        const ws = client.connectWebSocket();
        client.subscribeToJob(ws, jobId);

        // Wait for completion
        const results = await client.waitForCompletion(jobId);
        console.log('Results:', results);

        ws.close();
    } catch (error) {
        console.error('Error:', error.message);
    }
}

main();
```

## Troubleshooting

### Common Issues

#### API Connection Issues

**Problem**: Cannot connect to API server
```bash
curl: (7) Failed to connect to localhost port 8000: Connection refused
```

**Solutions**:
1. Ensure API server is running: `async-scraper api`
2. Check if port 8000 is available: `netstat -an | grep 8000`
3. Try different port: `async-scraper api --port 8080`

#### Authentication Errors

**Problem**: API key authentication fails
```json
{"error": "API key required"}
```

**Solutions**:
1. Include API key in header: `-H "X-API-Key: your-key"`
2. Check API key format: must be at least 8 characters
3. Verify key in configuration: `async-scraper show-config`

#### Rate Limiting

**Problem**: Requests are being rate limited
```json
{"error": "Rate limit exceeded", "retry_after": 60}
```

**Solutions**:
1. Reduce request frequency
2. Increase rate limits in configuration
3. Use multiple API keys for higher throughput

#### Job Processing Issues

**Problem**: Jobs get stuck in "pending" status

**Solutions**:
1. Check API server logs for errors
2. Verify sufficient system resources (memory, network)
3. Restart API server if needed

**Problem**: Jobs fail with timeout errors

**Solutions**:
1. Increase timeout in configuration
2. Reduce concurrency settings
3. Check network connectivity to target sites

#### WebSocket Connection Issues

**Problem**: WebSocket connection fails immediately

**Solutions**:
1. Ensure API key is included in WebSocket URL
2. Check firewall settings for WebSocket traffic
3. Verify WebSocket is enabled in server configuration

### Debugging Tips

#### Enable Debug Logging

```bash
# CLI with debug logging
SCRAPER_DEBUG=true async-scraper scrape companies.csv

# API server with debug logging
SCRAPER_LOGGING_LEVEL=DEBUG async-scraper api
```

#### Check Configuration

```bash
# Show current configuration
async-scraper show-config

# Test configuration validity
async-scraper test-config

# Validate custom config file
async-scraper test-config --config my-config.json
```

#### Monitor System Resources

```bash
# Check memory usage
free -h

# Check disk space
df -h

# Check network connections
netstat -an | grep :8000
```

#### API Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check (requires API key)
curl -H "X-API-Key: your-key" http://localhost:8000/health/detailed
```

### Performance Optimization

#### For High-Volume Processing

1. **Increase Concurrency**:
```json
{
  "concurrency": {
    "max_concurrent_domains": 20,
    "max_concurrent_per_domain": 10,
    "global_rate_limit": 5.0
  }
}
```

2. **Enable L2 Caching**:
```json
{
  "cache": {
    "l1_enabled": true,
    "l2_enabled": true,
    "l2_redis_url": "redis://localhost:6379"
  }
}
```

3. **Optimize Timeouts**:
```json
{
  "scraping": {
    "timeout": 20.0,
    "max_crawl_depth": 2
  }
}
```

#### For Memory-Constrained Systems

1. **Reduce Cache Sizes**:
```json
{
  "cache": {
    "l1_max_size": 500,
    "l3_enabled": false
  }
}
```

2. **Lower Concurrency**:
```json
{
  "concurrency": {
    "max_concurrent_domains": 5,
    "max_concurrent_per_domain": 2
  }
}
```

### Getting Help

1. **Check Documentation**: Review this guide and the Architecture.md file
2. **Enable Debug Logging**: Set `SCRAPER_DEBUG=true` for detailed logs
3. **Test Configuration**: Use `async-scraper test-config` to validate setup
4. **Check GitHub Issues**: Look for similar problems and solutions
5. **Health Checks**: Use `/health/detailed` endpoint for system diagnostics

This comprehensive usage guide should help you make the most of Async_Scraper's capabilities, whether you're using the CLI for simple tasks or integrating the REST API into complex applications.