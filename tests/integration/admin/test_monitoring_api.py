"""Integration tests for admin monitoring API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from scraper.api.main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Admin authentication headers."""
    return {"X-API-Key": "test-admin-key-123456"}


@pytest.mark.asyncio
async def test_get_system_health(client):
    """Test getting system health status."""
    with patch('scraper.core.monitoring.health_checker') as mock_health_checker:
        mock_health_data = {
            "status": "healthy",
            "timestamp": 1234567890.0,
            "checks": {
                "database": {
                    "status": "healthy",
                    "message": "Database connection healthy",
                    "duration_ms": 5.0
                },
                "queue": {
                    "status": "healthy", 
                    "message": "Queue system healthy",
                    "duration_ms": 3.0
                }
            },
            "summary": {
                "total_checks": 2,
                "healthy": 2,
                "unhealthy": 0
            }
        }
        
        mock_health_checker.get_system_health = AsyncMock(return_value=mock_health_data)
        
        response = client.get("/admin/monitoring/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "checks" in data
        assert "summary" in data
        assert data["summary"]["healthy"] == 2


@pytest.mark.asyncio
async def test_get_specific_health_check(client):
    """Test getting a specific health check result."""
    with patch('scraper.core.monitoring.health_checker') as mock_health_checker:
        from scraper.core.monitoring.health import HealthCheckResult, HealthStatus
        
        mock_result = HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database connection healthy",
            duration_ms=10.0,
            details={"connected": True}
        )
        
        mock_health_checker.run_check = AsyncMock(return_value=mock_result)
        
        response = client.get("/admin/monitoring/health/database")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "database"
        assert data["status"] == "healthy"
        assert data["message"] == "Database connection healthy"
        assert data["details"]["connected"] is True


@pytest.mark.asyncio
async def test_get_prometheus_metrics(client):
    """Test getting Prometheus metrics."""
    with patch('scraper.core.monitoring.metrics_manager') as mock_metrics_manager:
        mock_metrics_data = """# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/health",status_code="200"} 10.0
"""
        mock_content_type = "text/plain; version=0.0.4; charset=utf-8"
        
        mock_metrics_manager.get_metrics_data.return_value = mock_metrics_data
        mock_metrics_manager.get_content_type.return_value = mock_content_type
        
        response = client.get("/admin/monitoring/metrics")
        
        assert response.status_code == 200
        assert "http_requests_total" in response.text
        assert response.headers["content-type"] == mock_content_type


@pytest.mark.asyncio
async def test_get_system_stats(client):
    """Test getting comprehensive system statistics."""
    with patch('scraper.core.tenant.get_tenant_manager') as mock_get_tenant_manager, \
         patch('scraper.queue.get_queue_manager') as mock_get_queue_manager, \
         patch('scraper.core.proxy.get_proxy_manager') as mock_get_proxy_manager, \
         patch('scraper.core.monitoring.health_checker') as mock_health_checker, \
         patch('psutil.cpu_percent') as mock_cpu, \
         patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.disk_usage') as mock_disk:
        
        # Mock all the dependencies
        mock_tenant_manager = AsyncMock()
        mock_tenant_manager.get_tenant_usage_stats.return_value = {
            "total_tenants": 5,
            "active_tenants": 4
        }
        mock_get_tenant_manager.return_value = mock_tenant_manager
        
        mock_queue_manager = AsyncMock()
        mock_queue_manager.get_queue_stats.return_value = {
            "pending_jobs": 10,
            "active_jobs": 5
        }
        mock_get_queue_manager.return_value = mock_queue_manager
        
        mock_proxy_manager = AsyncMock()
        mock_proxy_manager.get_stats.return_value = {
            "total_proxies": 3,
            "healthy_proxies": 2
        }
        mock_get_proxy_manager.return_value = mock_proxy_manager
        
        mock_health_data = {
            "status": "healthy",
            "timestamp": 1234567890.0,
            "summary": {"healthy": 5, "unhealthy": 0, "total_checks": 5}
        }
        mock_health_checker.get_system_health = AsyncMock(return_value=mock_health_data)
        
        # Mock psutil
        mock_cpu.return_value = 25.5
        
        class MockMemory:
            percent = 60.0
            total = 8 * 1024**3  # 8GB
            available = 3 * 1024**3  # 3GB
            
        mock_memory.return_value = MockMemory()
        
        class MockDisk:
            total = 500 * 1024**3  # 500GB
            used = 200 * 1024**3   # 200GB
            free = 300 * 1024**3   # 300GB
            
        mock_disk.return_value = MockDisk()
        
        response = client.get("/admin/monitoring/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "system" in data
        assert data["system"]["cpu_percent"] == 25.5
        assert data["system"]["memory_percent"] == 60.0
        
        assert "health" in data
        assert data["health"]["overall_status"] == "healthy"
        
        assert "tenants" in data
        assert data["tenants"]["total_tenants"] == 5
        
        assert "queue" in data
        assert data["queue"]["pending_jobs"] == 10
        
        assert "proxies" in data
        assert data["proxies"]["total_proxies"] == 3


@pytest.mark.asyncio
async def test_reset_health_checks(client):
    """Test resetting health checks."""
    with patch('scraper.core.monitoring.health_checker') as mock_health_checker:
        mock_health_checker.run_all_checks = AsyncMock(return_value={})
        
        response = client.post("/admin/monitoring/health/reset")
        
        assert response.status_code == 200
        data = response.json()
        assert "reset" in data["message"].lower()
        mock_health_checker.run_all_checks.assert_called_once()


@pytest.mark.asyncio
async def test_get_performance_metrics(client):
    """Test getting performance metrics."""
    with patch('psutil.cpu_percent') as mock_cpu, \
         patch('psutil.cpu_count') as mock_cpu_count, \
         patch('psutil.getloadavg') as mock_load, \
         patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.net_io_counters') as mock_network, \
         patch('psutil.disk_io_counters') as mock_disk_io:
        
        # Mock system metrics
        mock_cpu.return_value = 15.5
        mock_cpu_count.return_value = 4
        mock_load.return_value = (0.5, 0.6, 0.7)
        
        class MockMemory:
            percent = 45.0
            total = 16 * 1024**3
            available = 8 * 1024**3
            used = 7 * 1024**3
            
        mock_memory.return_value = MockMemory()
        
        class MockNetwork:
            bytes_sent = 1024000
            bytes_recv = 2048000
            packets_sent = 5000
            packets_recv = 8000
            
        mock_network.return_value = MockNetwork()
        
        class MockDiskIO:
            read_bytes = 10240000
            write_bytes = 5120000
            read_count = 1000
            write_count = 500
            
        mock_disk_io.return_value = MockDiskIO()
        
        response = client.get("/admin/monitoring/performance")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "cpu" in data
        assert data["cpu"]["percent"] == 15.5
        assert data["cpu"]["count"] == 4
        assert data["cpu"]["load_avg_1min"] == 0.5
        
        assert "memory" in data
        assert data["memory"]["percent"] == 45.0
        
        assert "network" in data
        assert data["network"]["bytes_sent"] == 1024000
        
        assert "disk" in data
        assert data["disk"]["read_bytes"] == 10240000


@pytest.mark.asyncio
async def test_error_handling_in_monitoring_endpoints(client):
    """Test error handling in monitoring endpoints."""
    with patch('scraper.core.monitoring.health_checker') as mock_health_checker:
        mock_health_checker.get_system_health.side_effect = Exception("Health check failed")
        
        response = client.get("/admin/monitoring/health")
        
        assert response.status_code == 500
        data = response.json()
        assert "failed to get system health" in data["detail"].lower()


@pytest.mark.asyncio
async def test_metrics_endpoint_error_handling(client):
    """Test error handling in metrics endpoint."""
    with patch('scraper.core.monitoring.metrics_manager') as mock_metrics_manager:
        mock_metrics_manager.get_metrics_data.side_effect = Exception("Metrics error")
        
        response = client.get("/admin/monitoring/metrics")
        
        assert response.status_code == 500
        data = response.json()
        assert "failed to get metrics" in data["detail"].lower()


@pytest.mark.asyncio
async def test_stats_endpoint_with_missing_dependencies(client):
    """Test stats endpoint when some dependencies are unavailable."""
    with patch('scraper.core.tenant.get_tenant_manager') as mock_get_tenant_manager, \
         patch('scraper.queue.get_queue_manager') as mock_get_queue_manager, \
         patch('scraper.core.proxy.get_proxy_manager') as mock_get_proxy_manager, \
         patch('scraper.core.monitoring.health_checker') as mock_health_checker:
        
        # Make tenant manager fail
        mock_get_tenant_manager.side_effect = Exception("Tenant manager not available")
        
        # But other services work
        mock_queue_manager = AsyncMock()
        mock_queue_manager.get_queue_stats.return_value = {"pending_jobs": 0}
        mock_get_queue_manager.return_value = mock_queue_manager
        
        mock_proxy_manager = AsyncMock()
        mock_proxy_manager.get_stats.return_value = {"total_proxies": 0}
        mock_get_proxy_manager.return_value = mock_proxy_manager
        
        mock_health_data = {"status": "healthy", "timestamp": 1234567890.0, "summary": {}}
        mock_health_checker.get_system_health = AsyncMock(return_value=mock_health_data)
        
        response = client.get("/admin/monitoring/stats")
        
        # Should still return 500 because of the exception
        assert response.status_code == 500


@pytest.mark.asyncio 
async def test_health_check_with_unhealthy_system(client):
    """Test health check endpoint with unhealthy system."""
    with patch('scraper.core.monitoring.health_checker') as mock_health_checker:
        mock_health_data = {
            "status": "unhealthy",
            "timestamp": 1234567890.0,
            "checks": {
                "database": {
                    "status": "unhealthy",
                    "message": "Connection failed",
                    "duration_ms": 5000.0
                }
            },
            "summary": {
                "total_checks": 1,
                "healthy": 0,
                "unhealthy": 1,
                "required_unhealthy": ["database"]
            }
        }
        
        mock_health_checker.get_system_health = AsyncMock(return_value=mock_health_data)
        
        response = client.get("/admin/monitoring/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["summary"]["unhealthy"] == 1
        assert "database" in data["summary"]["required_unhealthy"]