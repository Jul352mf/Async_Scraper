"""Tests for health checking system."""

import pytest
from unittest.mock import patch, AsyncMock
from scraper.core.monitoring.health import HealthChecker, HealthStatus, HealthCheckConfig


@pytest.fixture
async def health_checker():
    """Create health checker for testing."""
    checker = HealthChecker()
    await checker.initialize()
    return checker


@pytest.mark.asyncio
async def test_health_checker_initialization(health_checker):
    """Test health checker initialization."""
    assert len(health_checker._checks) > 0
    assert "database" in health_checker._checks
    assert "queue" in health_checker._checks
    assert "memory" in health_checker._checks


@pytest.mark.asyncio
async def test_register_and_unregister_check(health_checker):
    """Test check registration and unregistration."""
    async def dummy_check():
        return {
            "name": "dummy",
            "status": HealthStatus.HEALTHY,
            "message": "OK",
            "duration_ms": 1.0
        }
    
    config = HealthCheckConfig(
        name="dummy",
        check_func=dummy_check,
        timeout_seconds=1.0,
        required=False
    )
    
    # Register check
    health_checker.register_check(config)
    assert "dummy" in health_checker._checks
    
    # Unregister check
    health_checker.unregister_check("dummy")
    assert "dummy" not in health_checker._checks


@pytest.mark.asyncio 
async def test_run_specific_check(health_checker):
    """Test running a specific health check."""
    # Mock the database check
    with patch.object(health_checker, '_check_database_health', new_callable=AsyncMock) as mock_check:
        from scraper.core.monitoring.health import HealthCheckResult
        mock_check.return_value = HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database is healthy",
            duration_ms=10.0
        )
        
        result = await health_checker.run_check("database")
        
        assert result.name == "database"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Database is healthy"
        mock_check.assert_called_once()


@pytest.mark.asyncio
async def test_run_nonexistent_check(health_checker):
    """Test running a nonexistent health check."""
    result = await health_checker.run_check("nonexistent")
    
    assert result.name == "nonexistent"
    assert result.status == HealthStatus.UNKNOWN
    assert "not found" in result.message.lower()


@pytest.mark.asyncio
async def test_run_all_checks(health_checker):
    """Test running all health checks."""
    # Mock all check functions to avoid external dependencies
    with patch.object(health_checker, '_check_database_health', new_callable=AsyncMock) as mock_db, \
         patch.object(health_checker, '_check_queue_health', new_callable=AsyncMock) as mock_queue, \
         patch.object(health_checker, '_check_memory_usage', new_callable=AsyncMock) as mock_memory, \
         patch.object(health_checker, '_check_disk_space', new_callable=AsyncMock) as mock_disk, \
         patch.object(health_checker, '_check_external_connectivity', new_callable=AsyncMock) as mock_external:
        
        from scraper.core.monitoring.health import HealthCheckResult
        
        # Setup mock returns
        mock_db.return_value = HealthCheckResult("database", HealthStatus.HEALTHY, "OK", 5.0)
        mock_queue.return_value = HealthCheckResult("queue", HealthStatus.HEALTHY, "OK", 3.0)
        mock_memory.return_value = HealthCheckResult("memory", HealthStatus.HEALTHY, "OK", 1.0)
        mock_disk.return_value = HealthCheckResult("disk", HealthStatus.HEALTHY, "OK", 1.0)
        mock_external.return_value = HealthCheckResult("external_connectivity", HealthStatus.HEALTHY, "OK", 8.0)
        
        results = await health_checker.run_all_checks()
        
        assert len(results) == 5
        assert "database" in results
        assert "queue" in results
        assert all(result.status == HealthStatus.HEALTHY for result in results.values())


@pytest.mark.asyncio
async def test_get_system_health(health_checker):
    """Test getting overall system health."""
    # Mock all checks to return healthy
    with patch.object(health_checker, 'run_all_checks', new_callable=AsyncMock) as mock_run_all:
        from scraper.core.monitoring.health import HealthCheckResult
        
        mock_results = {
            "database": HealthCheckResult("database", HealthStatus.HEALTHY, "OK", 5.0),
            "queue": HealthCheckResult("queue", HealthStatus.HEALTHY, "OK", 3.0)
        }
        mock_run_all.return_value = mock_results
        
        health_data = await health_checker.get_system_health()
        
        assert health_data["status"] == "healthy"
        assert "timestamp" in health_data
        assert "checks" in health_data
        assert "summary" in health_data
        assert health_data["summary"]["total_checks"] == 2
        assert health_data["summary"]["healthy"] == 2


@pytest.mark.asyncio
async def test_get_system_health_with_failures(health_checker):
    """Test system health with some failures."""
    with patch.object(health_checker, 'run_all_checks', new_callable=AsyncMock) as mock_run_all:
        from scraper.core.monitoring.health import HealthCheckResult
        
        mock_results = {
            "database": HealthCheckResult("database", HealthStatus.UNHEALTHY, "Connection failed", 5.0),
            "queue": HealthCheckResult("queue", HealthStatus.HEALTHY, "OK", 3.0)
        }
        mock_run_all.return_value = mock_results
        
        # Set database as required check
        health_checker._checks["database"].required = True
        
        health_data = await health_checker.get_system_health()
        
        assert health_data["status"] == "unhealthy"  # Required check failed
        assert health_data["summary"]["unhealthy"] == 1
        assert len(health_data["summary"]["required_unhealthy"]) == 1


@pytest.mark.asyncio
async def test_background_checks_start_stop(health_checker):
    """Test background health checking."""
    # Stop any existing background checks
    await health_checker.stop_background_checks()
    
    # Start background checks
    await health_checker.start_background_checks()
    assert health_checker._running is True
    assert health_checker._background_task is not None
    
    # Stop background checks
    await health_checker.stop_background_checks()
    assert health_checker._running is False


@pytest.mark.asyncio
async def test_cached_results(health_checker):
    """Test cached health check results."""
    # Mock a check result
    from scraper.core.monitoring.health import HealthCheckResult
    test_result = HealthCheckResult("test", HealthStatus.HEALTHY, "OK", 1.0)
    health_checker._last_results["test"] = test_result
    
    cached_results = await health_checker.get_cached_results()
    
    assert "test" in cached_results
    assert cached_results["test"].name == "test"
    assert cached_results["test"].status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_cleanup(health_checker):
    """Test health checker cleanup."""
    await health_checker.cleanup()
    
    assert len(health_checker._checks) == 0
    assert len(health_checker._last_results) == 0