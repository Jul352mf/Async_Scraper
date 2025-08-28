"""
Integration tests for proxy management API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from scraper.api.main import create_app
from scraper.core.proxy import ProxyManager
from scraper.core.proxy.models import ProxyConfig


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Authentication headers for API requests."""
    return {"X-API-Key": "test-api-key-123456"}


@pytest.fixture
async def proxy_manager():
    """Create a test proxy manager."""
    config = ProxyConfig(enabled=True)
    manager = ProxyManager(config)
    await manager.initialize()
    return manager


class TestProxyManagementAPI:
    """Test proxy management API endpoints."""
    
    def test_list_proxies_empty(self, client, auth_headers):
        """Test listing proxies when none exist."""
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.list_proxies.return_value = []
            mock_get_manager.return_value = mock_manager
            
            response = client.get("/api/v1/proxy/proxies", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 0
    
    def test_create_proxy_success(self, client, auth_headers):
        """Test creating a new proxy successfully."""
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager
            
            proxy_data = {
                "url": "http://proxy.example.com:8080",
                "description": "Test proxy",
                "country": "US",
                "tags": ["fast", "reliable"]
            }
            
            response = client.post("/api/v1/proxy/proxies", json=proxy_data, headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["url"] == proxy_data["url"]
            assert data["description"] == proxy_data["description"]
            assert data["country"] == proxy_data["country"]
            assert data["tags"] == proxy_data["tags"]
            assert "id" in data
            assert mock_manager.add_proxy.called
    
    def test_create_proxy_invalid_url(self, client, auth_headers):
        """Test creating proxy with invalid URL."""
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.add_proxy.side_effect = ValueError("Invalid proxy URL")
            mock_get_manager.return_value = mock_manager
            
            proxy_data = {
                "url": "invalid-url"
            }
            
            response = client.post("/api/v1/proxy/proxies", json=proxy_data, headers=auth_headers)
            
            assert response.status_code == 400
            assert "Invalid proxy URL" in response.json()["detail"]
    
    def test_get_proxy_success(self, client, auth_headers):
        """Test getting a specific proxy."""
        from scraper.core.proxy.models import Proxy
        
        test_proxy = Proxy(
            url="http://proxy.example.com:8080",
            description="Test proxy"
        )
        
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_proxy.return_value = test_proxy
            mock_get_manager.return_value = mock_manager
            
            response = client.get(f"/api/v1/proxy/proxies/{test_proxy.id}", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == test_proxy.id
            assert data["url"] == test_proxy.url
            assert data["description"] == test_proxy.description
    
    def test_get_proxy_not_found(self, client, auth_headers):
        """Test getting non-existent proxy."""
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_proxy.return_value = None
            mock_get_manager.return_value = mock_manager
            
            response = client.get("/api/v1/proxy/proxies/non-existent", headers=auth_headers)
            
            assert response.status_code == 404
            assert "Proxy not found" in response.json()["detail"]
    
    def test_update_proxy_success(self, client, auth_headers):
        """Test updating proxy configuration."""
        from scraper.core.proxy.models import Proxy
        
        test_proxy = Proxy(url="http://proxy.example.com:8080")
        test_proxy.description = "Updated description"
        test_proxy.country = "UK"
        
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.update_proxy.return_value = True
            mock_manager.get_proxy.return_value = test_proxy
            mock_get_manager.return_value = mock_manager
            
            update_data = {
                "description": "Updated description",
                "country": "UK"
            }
            
            response = client.put(f"/api/v1/proxy/proxies/{test_proxy.id}", json=update_data, headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["description"] == "Updated description"
            assert data["country"] == "UK"
    
    def test_delete_proxy_success(self, client, auth_headers):
        """Test deleting a proxy."""
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.remove_proxy.return_value = True
            mock_get_manager.return_value = mock_manager
            
            response = client.delete("/api/v1/proxy/proxies/test-id", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert "deleted successfully" in data["message"]
    
    def test_delete_proxy_not_found(self, client, auth_headers):
        """Test deleting non-existent proxy."""
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.remove_proxy.return_value = False
            mock_get_manager.return_value = mock_manager
            
            response = client.delete("/api/v1/proxy/proxies/non-existent", headers=auth_headers)
            
            assert response.status_code == 404
    
    def test_check_proxy_health(self, client, auth_headers):
        """Test checking proxy health."""
        from scraper.core.proxy.models import Proxy, ProxyStatus
        
        test_proxy = Proxy(url="http://proxy.example.com:8080")
        test_proxy.health.status = ProxyStatus.HEALTHY
        test_proxy.health.response_time = 0.5
        
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.check_proxy_health.return_value = True
            mock_manager.get_proxy.return_value = test_proxy
            mock_get_manager.return_value = mock_manager
            
            response = client.post(f"/api/v1/proxy/proxies/{test_proxy.id}/health-check", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["health_check_passed"] is True
            assert data["status"] == "healthy"
            assert data["response_time"] == 0.5
    
    def test_check_all_proxies_health(self, client, auth_headers):
        """Test checking health of all proxies."""
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.check_all_proxies_health.return_value = {
                "proxy1": True,
                "proxy2": False,
                "proxy3": True
            }
            mock_get_manager.return_value = mock_manager
            
            response = client.post("/api/v1/proxy/proxies/health-check-all", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_proxies_checked"] == 3
            assert data["healthy_proxies"] == 2
            assert data["unhealthy_proxies"] == 1
    
    def test_get_proxy_stats(self, client, auth_headers):
        """Test getting proxy system statistics."""
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_proxy_stats.return_value = {
                "total_proxies": 5,
                "enabled_proxies": 4,
                "healthy_proxies": 3,
                "average_response_time": 0.75,
                "status_distribution": {
                    "healthy": 3,
                    "unhealthy": 1,
                    "blacklisted": 1
                },
                "rotation_strategy": "round_robin"
            }
            mock_get_manager.return_value = mock_manager
            
            response = client.get("/api/v1/proxy/stats", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_proxies"] == 5
            assert data["enabled_proxies"] == 4
            assert data["healthy_proxies"] == 3
            assert data["rotation_strategy"] == "round_robin"
    
    def test_get_proxy_config(self, client, auth_headers):
        """Test getting proxy configuration."""
        from scraper.core.proxy.models import ProxyConfig, ProxyRotationStrategy
        
        test_config = ProxyConfig(
            enabled=True,
            rotation_strategy=ProxyRotationStrategy.ROUND_ROBIN,
            health_check_interval=300
        )
        
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.config = test_config
            mock_get_manager.return_value = mock_manager
            
            response = client.get("/api/v1/proxy/config", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True
            assert data["rotation_strategy"] == "round_robin"
            assert data["health_check_interval"] == 300
    
    def test_update_proxy_config(self, client, auth_headers):
        """Test updating proxy configuration."""
        from scraper.core.proxy.models import ProxyConfig, ProxyRotationStrategy
        
        test_config = ProxyConfig(
            enabled=True,
            rotation_strategy=ProxyRotationStrategy.RANDOM,
            health_check_interval=600
        )
        
        with patch('scraper.api.routes.proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.config = test_config
            mock_manager.set_rotation_strategy = AsyncMock()
            mock_manager.set_geographic_preference = AsyncMock()
            mock_get_manager.return_value = mock_manager
            
            config_update = {
                "rotation_strategy": "random",
                "health_check_interval": 600,
                "geographic_preference": "US"
            }
            
            response = client.put("/api/v1/proxy/config", json=config_update, headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["rotation_strategy"] == "random"
            assert data["health_check_interval"] == 600
    
    def test_api_requires_authentication(self, client):
        """Test that API endpoints require authentication."""
        endpoints = [
            ("/api/v1/proxy/proxies", "GET"),
            ("/api/v1/proxy/proxies", "POST"),
            ("/api/v1/proxy/proxies/test-id", "GET"),
            ("/api/v1/proxy/proxies/test-id", "PUT"),
            ("/api/v1/proxy/proxies/test-id", "DELETE"),
            ("/api/v1/proxy/stats", "GET"),
            ("/api/v1/proxy/config", "GET"),
        ]
        
        for endpoint, method in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            elif method == "PUT":
                response = client.put(endpoint, json={})
            elif method == "DELETE":
                response = client.delete(endpoint)
            
            # Should require authentication
            assert response.status_code in [401, 403], f"Endpoint {method} {endpoint} should require auth"


class TestProxyIntegration:
    """Test proxy system integration with other components."""
    
    def test_proxy_with_web_client_integration(self):
        """Test proxy integration with web client."""
        # This would test the integration between proxy manager and web client
        # For now, we'll test that the web client can be initialized with proxy support
        from scraper.core.config import Config, ProxyConfig
        from scraper.services.web_client import WebClient
        
        config = Config()
        config.proxy = ProxyConfig(
            enabled=True,
            proxy_urls=["http://proxy.example.com:8080"]
        )
        
        web_client = WebClient(config)
        
        # Should initialize without errors
        assert web_client._proxy_manager is not None
        assert len(web_client._proxy_manager.list_proxies()) > 0
    
    def test_proxy_with_browser_manager_integration(self):
        """Test proxy integration with browser manager."""
        from scraper.core.proxy.models import Proxy
        from scraper.services.browser_manager import BrowserManager
        
        # Create proxy manager with test proxy
        proxy = Proxy(url="http://proxy.example.com:8080")
        proxy.update_health(success=True)
        
        proxy_manager = AsyncMock()
        proxy_manager.get_next_proxy.return_value = proxy
        
        browser_manager = BrowserManager(proxy_manager=proxy_manager)
        
        # Should initialize without errors
        assert browser_manager.proxy_manager is not None