# Async Scraper

High-performance, async-first web scraping framework that can turn a list of company names or domains into validated email leads.

## Features

- **Async-first architecture** using Python 3.11+ asyncio
- **Multi-layer caching** (L1/L2/L3) for performance optimization
- **Adaptive rate limiting** to respect server limits
- **Modular design** with clean separation of concerns
- **Configuration management** with Pydantic
- **Structured logging** with contextual information
- **CLI interface** with progress tracking
- **Comprehensive testing** with pytest

## Installation

```bash
# Clone the repository
git clone https://github.com/Jul352mf/Async_Scraper.git
cd Async_Scraper

# Install in development mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

## Quick Start

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

## Configuration

The framework uses Pydantic for configuration management. You can:

1. Use environment variables (prefixed with `SCRAPER_`)
2. Create a `.env` file
3. Use a JSON configuration file

Example configuration:

```json
{
  "debug": false,
  "cache": {
    "l1_enabled": true,
    "l1_max_size": 1000,
    "l2_enabled": false
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
  }
}
```

## Architecture

The framework follows a modular architecture:

```
scraper/
├── core/           # Core functionality (config, logging, utils)
├── data/           # Data loading, saving, and cleaning
├── services/       # Web scraping services and clients
├── cli/            # Command-line interface
└── tests/          # Comprehensive test suite
```

## Development

```bash
# Run tests
pytest tests/

# Run tests with coverage
pytest tests/ --cov=scraper

# Format code
black scraper/ tests/

# Lint code
ruff scraper/ tests/

# Type checking
mypy scraper/
```

## License

MIT License - see LICENSE file for details.
