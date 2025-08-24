# GitHub Copilot Instructions

## Repository Context
This repository contains **Async_Scraper**, a production-ready async web scraping framework. When working with this codebase, prioritize async patterns, proper error handling, and maintainable code structure.

## Key Development Guidelines

### Code Quality Standards
- **Type hints are mandatory** - All functions must have proper type annotations
- **Async-first approach** - Use async/await for all I/O operations
- **Error handling** - Always handle potential failures with proper logging
- **Resource cleanup** - Ensure proper cleanup of async resources (connections, files)

### Pull Request Guidelines
- **Run full test suite** before submitting: `pytest tests/ --cov=scraper`
- **Maintain coverage** - Keep test coverage above 25% (aim for higher)
- **Format code** - Use `black scraper/ tests/` before committing
- **Lint code** - Run `ruff scraper/ tests/` to catch issues
- **Type check** - Run `mypy scraper/` to ensure type safety

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
from scraper.core.config import get_global_config

config = get_global_config()
timeout = config.scraping.timeout
```

### Testing Patterns

#### Async Test Structure
```python
import pytest
from aioresponses import aioresponses

@pytest.mark.asyncio
async def test_email_extraction():
    with aioresponses() as mock:
        mock.get("https://example.com", payload={"content": "test@example.com"})
        # Test implementation
```

#### Mock External Services
- Use `aioresponses` for HTTP mocking
- Mock Redis connections when Redis cache is involved  
- Use temporary files for file I/O testing

### File Organization Rules
- **Core functionality** goes in `scraper/core/`
- **Business logic** goes in `scraper/services/`  
- **Data processing** goes in `scraper/data/`
- **CLI commands** go in `scraper/cli/`
- **Tests mirror source structure** in `tests/unit/` and `tests/integration/`

### Performance Considerations
- Use connection pooling for HTTP requests
- Implement proper backpressure with semaphores
- Cache expensive operations appropriately
- Monitor memory usage with large datasets

### Security Guidelines  
- Never commit API keys or credentials
- Validate all external inputs
- Use environment variables for configuration
- Sanitize data before processing

## Git Workflow
- Create feature branches from `main`
- Use descriptive commit messages
- Squash commits before merging
- Update documentation when adding features

## Documentation Standards
- Update docstrings for new public methods
- Include usage examples for complex functionality
- Update README.md for significant changes
- Maintain this instruction file for major architectural changes

Remember: This is an async-first framework. When in doubt, use async patterns and proper resource management.