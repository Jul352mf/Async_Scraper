"""Integration tests for admin tenant API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from scraper.api.main import create_app
from scraper.core.tenant.models import TenantPlan, TenantStatus


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Admin authentication headers."""
    return {"X-API-Key": "test-admin-key-123456"}


@pytest.fixture
def sample_tenant_data():
    """Sample tenant data for testing."""
    return {
        "tenant_id": "test-tenant-123",
        "config": {
            "tenant_id": "test-tenant-123",
            "name": "Test Company",
            "contact_email": "admin@testcompany.com",
            "plan": "basic",
            "status": "active",
            "organization": "Test Org"
        },
        "quotas": {
            "requests_per_hour": 1000,
            "concurrent_jobs": 5,
            "javascript_enabled": True,
            "proxy_enabled": False
        },
        "usage": {
            "requests_this_hour": 50,
            "active_jobs": 2,
            "total_jobs": 100
        },
        "usage_percentage": {
            "requests_hour": 5.0,
            "concurrent_jobs": 40.0
        }
    }


@pytest.mark.asyncio
async def test_create_tenant(client, admin_headers):
    """Test creating a new tenant."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        from scraper.core.tenant.models import TenantModel
        mock_tenant = AsyncMock()
        mock_tenant.to_dict.return_value = {
            "tenant_id": "new-tenant-123",
            "config": {"name": "New Company"},
            "quotas": {},
            "usage": {},
            "usage_percentage": {}
        }
        mock_manager.create_tenant.return_value = mock_tenant
        
        response = client.post(
            "/admin/tenants/",
            json={
                "name": "New Company",
                "contact_email": "admin@newcompany.com",
                "plan": "basic"
            },
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "new-tenant-123"


@pytest.mark.asyncio
async def test_list_tenants(client, admin_headers, sample_tenant_data):
    """Test listing tenants."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        mock_tenant = AsyncMock()
        mock_tenant.to_dict.return_value = sample_tenant_data
        mock_manager.list_tenants.return_value = [mock_tenant]
        
        response = client.get("/admin/tenants/", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["tenant_id"] == "test-tenant-123"


@pytest.mark.asyncio
async def test_get_tenant(client, admin_headers, sample_tenant_data):
    """Test getting a specific tenant."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        mock_tenant = AsyncMock()
        mock_tenant.to_dict.return_value = sample_tenant_data
        mock_manager.get_tenant.return_value = mock_tenant
        
        response = client.get("/admin/tenants/test-tenant-123", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "test-tenant-123"
        assert data["config"]["name"] == "Test Company"


@pytest.mark.asyncio
async def test_get_nonexistent_tenant(client, admin_headers):
    """Test getting a nonexistent tenant."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        mock_manager.get_tenant.return_value = None
        
        response = client.get("/admin/tenants/nonexistent", headers=admin_headers)
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_update_tenant(client, admin_headers, sample_tenant_data):
    """Test updating a tenant."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        updated_data = sample_tenant_data.copy()
        updated_data["config"]["name"] = "Updated Company"
        
        mock_tenant = AsyncMock()
        mock_tenant.to_dict.return_value = updated_data
        mock_manager.update_tenant.return_value = mock_tenant
        
        response = client.patch(
            "/admin/tenants/test-tenant-123",
            json={"name": "Updated Company"},
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["config"]["name"] == "Updated Company"


@pytest.mark.asyncio
async def test_update_tenant_plan(client, admin_headers, sample_tenant_data):
    """Test updating tenant plan."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        updated_data = sample_tenant_data.copy()
        updated_data["config"]["plan"] = "professional"
        
        mock_tenant = AsyncMock()
        mock_tenant.to_dict.return_value = updated_data
        mock_manager.update_tenant_plan.return_value = mock_tenant
        
        response = client.post(
            "/admin/tenants/test-tenant-123/plan?new_plan=professional",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["config"]["plan"] == "professional"


@pytest.mark.asyncio
async def test_suspend_tenant(client, admin_headers, sample_tenant_data):
    """Test suspending a tenant."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        suspended_data = sample_tenant_data.copy()
        suspended_data["config"]["status"] = "suspended"
        
        mock_tenant = AsyncMock()
        mock_tenant.to_dict.return_value = suspended_data
        mock_manager.suspend_tenant.return_value = mock_tenant
        
        response = client.post(
            "/admin/tenants/test-tenant-123/suspend",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["config"]["status"] == "suspended"


@pytest.mark.asyncio
async def test_reactivate_tenant(client, admin_headers, sample_tenant_data):
    """Test reactivating a tenant."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        mock_tenant = AsyncMock()
        mock_tenant.to_dict.return_value = sample_tenant_data
        mock_manager.reactivate_tenant.return_value = mock_tenant
        
        response = client.post(
            "/admin/tenants/test-tenant-123/reactivate",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["config"]["status"] == "active"


@pytest.mark.asyncio
async def test_delete_tenant(client, admin_headers):
    """Test deleting a tenant."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        mock_manager.delete_tenant.return_value = True
        
        response = client.delete("/admin/tenants/test-tenant-123", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"].lower()


@pytest.mark.asyncio
async def test_get_tenant_usage(client, admin_headers):
    """Test getting tenant usage information."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager, \
         patch('scraper.database.get_database_manager') as mock_get_db:
        
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        mock_tenant = AsyncMock()
        mock_tenant.to_dict.return_value = {
            "usage": {"requests_this_hour": 50},
            "quotas": {"requests_per_hour": 1000}
        }
        mock_tenant.get_usage_percentage.return_value = {"requests_hour": 5.0}
        mock_manager.get_tenant.return_value = mock_tenant
        
        # Mock database manager and isolation manager
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        with patch('scraper.core.tenant.isolation.TenantIsolationManager') as mock_isolation_class:
            mock_isolation = AsyncMock()
            mock_isolation_class.return_value = mock_isolation
            mock_isolation.get_tenant_storage_usage.return_value = {
                "result_count": 100,
                "storage_used_mb": 25.5
            }
            
            response = client.get("/admin/tenants/test-tenant-123/usage", headers=admin_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert "requests_this_hour" in data
            assert "result_count" in data


@pytest.mark.asyncio
async def test_cleanup_tenant_data(client, admin_headers):
    """Test cleaning up tenant data."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager, \
         patch('scraper.database.get_database_manager') as mock_get_db:
        
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        mock_tenant = AsyncMock()
        mock_manager.get_tenant.return_value = mock_tenant
        
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        
        with patch('scraper.core.tenant.isolation.TenantIsolationManager') as mock_isolation_class:
            mock_isolation = AsyncMock()
            mock_isolation_class.return_value = mock_isolation
            mock_isolation.cleanup_tenant_data.return_value = {
                "jobs_deleted": 10,
                "results_deleted": 25
            }
            
            response = client.post(
                "/admin/tenants/test-tenant-123/cleanup?retention_days=30",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "cleanup completed" in data["message"].lower()
            assert data["stats"]["jobs_deleted"] == 10


@pytest.mark.asyncio
async def test_list_tenants_with_filters(client, admin_headers):
    """Test listing tenants with various filters."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        mock_manager.list_tenants.return_value = []
        
        # Test with status filter
        response = client.get("/admin/tenants/?status=active", headers=admin_headers)
        assert response.status_code == 200
        
        # Test with plan filter
        response = client.get("/admin/tenants/?plan=basic", headers=admin_headers)
        assert response.status_code == 200
        
        # Test with pagination
        response = client.get("/admin/tenants/?limit=10&offset=0", headers=admin_headers)
        assert response.status_code == 200
        
        # Verify the manager was called with correct parameters
        mock_manager.list_tenants.assert_called()


@pytest.mark.asyncio
async def test_authentication_required(client):
    """Test that admin endpoints require authentication."""
    # Try to create tenant without API key
    response = client.post(
        "/admin/tenants/",
        json={"name": "Test", "contact_email": "test@test.com"}
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_error_handling(client, admin_headers):
    """Test error handling in admin endpoints."""
    with patch('scraper.core.tenant.manager.get_tenant_manager') as mock_get_manager:
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager
        mock_manager.create_tenant.side_effect = Exception("Database error")
        
        response = client.post(
            "/admin/tenants/",
            json={"name": "Test", "contact_email": "test@test.com"},
            headers=admin_headers
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "failed to create tenant" in data["detail"].lower()