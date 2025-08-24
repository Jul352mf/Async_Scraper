# Async Scraper Architecture Documentation

The `async_scraper_arch.py` module provides a high-performance, async-first web scraping framework with the following key features:

## Key Features

- **Asynchronous Request Handling**: Built on aiohttp for high-performance concurrent requests
- **Rate Limiting**: Token bucket algorithm to respect server resources
- **Session Management**: Connection pooling and reuse for efficiency
- **Error Handling & Retries**: Configurable retry logic with exponential backoff
- **Extensible Architecture**: Abstract base classes for custom response processing

## Core Components

### ScrapingConfig
Configuration class for customizing scraper behavior:
- `requests_per_second`: Rate limiting (default: 10.0)
- `timeout`: Request timeout in seconds (default: 30)
- `max_retries`: Maximum retry attempts (default: 3)
- `default_headers`: Default HTTP headers

### AsyncScraper
Main scraper class that handles individual and batch requests:
- `scrape()`: Single request method
- `scrape_batch()`: Concurrent batch processing
- Context manager support for automatic cleanup

### ScrapingSession
High-level session manager with convenience methods:
- `get()`: GET request helper
- `post()`: POST request helper  
- `get_many()`: Batch GET requests

## Basic Usage

### Simple Single Request
```python
import asyncio
from async_scraper_arch import ScrapingSession

async def scrape_single():
    async with ScrapingSession() as session:
        response = await session.get("https://example.com")
        print(f"Status: {response.status_code}")
        print(f"Content: {response.text}")

asyncio.run(scrape_single())
```

### Batch Requests with Rate Limiting
```python
import asyncio
from async_scraper_arch import ScrapingSession, ScrapingConfig

async def scrape_batch():
    config = ScrapingConfig(requests_per_second=5.0)
    
    async with ScrapingSession(config) as session:
        urls = ["https://example.com", "https://httpbin.org/json"]
        
        async for response in session.get_many(urls):
            print(f"Scraped {response.url}: {response.status_code}")

asyncio.run(scrape_batch())
```

### Custom Configuration
```python
from async_scraper_arch import ScrapingConfig

config = ScrapingConfig(
    requests_per_second=2.0,  # 2 requests per second
    timeout=60,               # 60 second timeout
    max_retries=5,            # 5 retry attempts
    default_headers={
        'User-Agent': 'MyBot/1.0'
    }
)
```

### Advanced Usage with Custom Processing
```python
from async_scraper_arch import ResponseProcessor, AsyncScraper, RequestData

class JSONProcessor(ResponseProcessor):
    async def process(self, response):
        if response.is_success:
            import json
            return json.loads(response.text)
        return None

async def scrape_with_processor():
    async with AsyncScraper() as scraper:
        request = RequestData(url="https://httpbin.org/json")
        data = await scraper.scrape(request, JSONProcessor())
        print(f"JSON data: {data}")
```

## Installation

1. Install dependencies:
```bash
pip install aiohttp>=3.8.0
```

2. Import and use:
```python
from async_scraper_arch import ScrapingSession, ScrapingConfig
```

## Error Handling

The framework provides robust error handling:
- Network errors trigger automatic retries
- Rate limiting prevents overwhelming servers
- Timeouts are configurable per request
- All errors are logged with appropriate detail levels

## Performance Considerations

- Use `ScrapingSession` for multiple related requests
- Configure `requests_per_second` based on target server capacity
- Adjust `connector_limit` and `connector_limit_per_host` for concurrency
- Use batch processing (`scrape_batch`, `get_many`) for efficiency