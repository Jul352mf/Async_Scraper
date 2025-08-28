"""Tests for metrics collection."""

import pytest
from unittest.mock import patch, AsyncMock
from scraper.core.monitoring.metrics import MetricsManager


@pytest.fixture
async def metrics_manager():
    """Create metrics manager for testing."""
    manager = MetricsManager()
    await manager.initialize()
    return manager


@pytest.mark.asyncio
async def test_metrics_manager_initialization(metrics_manager):
    """Test metrics manager initialization."""
    assert metrics_manager._initialized is True
    assert len(metrics_manager._metrics) > 0
    
    # Check that core metrics are registered
    assert "http_requests_total" in metrics_manager._metrics
    assert "job_duration_seconds" in metrics_manager._metrics
    assert "db_connections_active" in metrics_manager._metrics


@pytest.mark.asyncio
async def test_increment_counter(metrics_manager):
    """Test counter increment functionality."""
    # Test basic increment
    metrics_manager.increment_counter("http_requests_total", {"method": "GET", "endpoint": "/test", "status_code": "200", "tenant_id": "test"})
    
    # Test increment with custom amount
    metrics_manager.increment_counter("http_requests_total", {"method": "POST", "endpoint": "/test", "status_code": "201", "tenant_id": "test"}, amount=5)
    
    # Should not raise any exceptions


@pytest.mark.asyncio
async def test_set_gauge(metrics_manager):
    """Test gauge setting functionality."""
    metrics_manager.set_gauge("db_connections_active", 5, {"database_name": "test"})
    metrics_manager.set_gauge("app_start_time", 1234567890.0)
    
    # Should not raise any exceptions


@pytest.mark.asyncio
async def test_observe_histogram(metrics_manager):
    """Test histogram observation functionality."""
    metrics_manager.observe_histogram("http_request_duration_seconds", 0.5, {"method": "GET", "endpoint": "/test", "tenant_id": "test"})
    metrics_manager.observe_histogram("job_duration_seconds", 30.0, {"job_type": "scrape", "tenant_id": "test"})
    
    # Should not raise any exceptions


@pytest.mark.asyncio
async def test_time_operation_context_manager(metrics_manager):
    """Test timing context manager."""
    import asyncio
    
    with metrics_manager.time_operation("test_operation_duration", {"operation": "test"}):
        await asyncio.sleep(0.1)  # Simulate work
        
    # Should not raise any exceptions


@pytest.mark.asyncio
async def test_get_metrics_data(metrics_manager):
    """Test metrics data export."""
    # Add some metric data
    metrics_manager.increment_counter("http_requests_total", {"method": "GET", "endpoint": "/test", "status_code": "200", "tenant_id": "test"})
    metrics_manager.set_gauge("db_connections_active", 3, {"database_name": "test"})
    
    # Get metrics data
    data = metrics_manager.get_metrics_data()
    content_type = metrics_manager.get_content_type()
    
    assert isinstance(data, str)
    assert len(data) > 0
    assert "text/plain" in content_type


@pytest.mark.asyncio
async def test_nonexistent_metric_handling(metrics_manager):
    """Test handling of nonexistent metrics."""
    # These should log warnings but not raise exceptions
    metrics_manager.increment_counter("nonexistent_counter")
    metrics_manager.set_gauge("nonexistent_gauge", 1.0)
    metrics_manager.observe_histogram("nonexistent_histogram", 1.0)


@pytest.mark.asyncio
async def test_cleanup(metrics_manager):
    """Test metrics manager cleanup."""
    await metrics_manager.cleanup()
    assert metrics_manager._initialized is False
    assert len(metrics_manager._metrics) == 0