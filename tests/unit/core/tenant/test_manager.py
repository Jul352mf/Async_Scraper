"""Tests for tenant manager functionality."""

import pytest
from unittest.mock import AsyncMock, patch
from scraper.core.tenant.manager import TenantManager
from scraper.core.tenant.models import TenantModel, TenantPlan, TenantStatus


@pytest.fixture
async def tenant_manager():
    """Create tenant manager for testing."""
    # Mock database dependencies
    with patch('scraper.core.tenant.manager.get_database_manager') as mock_db:
        mock_db.return_value.fetchall.return_value = []  # No existing tenants
        
        manager = TenantManager()
        await manager.initialize()
        return manager


@pytest.mark.asyncio
async def test_tenant_manager_initialization(tenant_manager):
    """Test tenant manager initialization."""
    assert tenant_manager._initialized is True
    assert isinstance(tenant_manager._tenants, dict)
    assert isinstance(tenant_manager._api_key_to_tenant, dict)


@pytest.mark.asyncio
async def test_create_tenant(tenant_manager):
    """Test creating a new tenant."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock) as mock_save:
        tenant = await tenant_manager.create_tenant(
            name="Test Company",
            contact_email="admin@testcompany.com",
            plan=TenantPlan.PROFESSIONAL,
            organization="Test Org"
        )
        
        assert tenant.config.name == "Test Company"
        assert tenant.config.contact_email == "admin@testcompany.com"
        assert tenant.config.plan == TenantPlan.PROFESSIONAL
        assert tenant.config.organization == "Test Org"
        assert tenant.tenant_id in tenant_manager._tenants
        
        # Should have attempted to save to database
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_get_tenant(tenant_manager):
    """Test retrieving a tenant by ID."""
    # Create a tenant first
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock):
        created_tenant = await tenant_manager.create_tenant(
            name="Test Company",
            contact_email="admin@testcompany.com"
        )
        
        # Retrieve the tenant
        retrieved_tenant = await tenant_manager.get_tenant(created_tenant.tenant_id)
        
        assert retrieved_tenant is not None
        assert retrieved_tenant.tenant_id == created_tenant.tenant_id
        assert retrieved_tenant.config.name == "Test Company"


@pytest.mark.asyncio
async def test_get_nonexistent_tenant(tenant_manager):
    """Test retrieving a nonexistent tenant."""
    tenant = await tenant_manager.get_tenant("nonexistent-id")
    assert tenant is None


@pytest.mark.asyncio
async def test_list_tenants(tenant_manager):
    """Test listing tenants with filters."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock):
        # Create multiple tenants
        tenant1 = await tenant_manager.create_tenant("Company 1", "admin1@test.com", TenantPlan.FREE)
        tenant2 = await tenant_manager.create_tenant("Company 2", "admin2@test.com", TenantPlan.BASIC)
        tenant3 = await tenant_manager.create_tenant("Company 3", "admin3@test.com", TenantPlan.PROFESSIONAL)
        
        # List all tenants
        all_tenants = await tenant_manager.list_tenants()
        assert len(all_tenants) == 3
        
        # Filter by plan
        basic_tenants = await tenant_manager.list_tenants(plan=TenantPlan.BASIC)
        assert len(basic_tenants) == 1
        assert basic_tenants[0].config.name == "Company 2"
        
        # Filter by status
        active_tenants = await tenant_manager.list_tenants(status=TenantStatus.ACTIVE)
        assert len(active_tenants) == 3  # All are active by default
        
        # Test pagination
        first_page = await tenant_manager.list_tenants(limit=2, offset=0)
        assert len(first_page) == 2
        
        second_page = await tenant_manager.list_tenants(limit=2, offset=2)
        assert len(second_page) == 1


@pytest.mark.asyncio
async def test_update_tenant(tenant_manager):
    """Test updating tenant configuration."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock):
        # Create a tenant
        tenant = await tenant_manager.create_tenant("Original Name", "original@test.com")
        original_id = tenant.tenant_id
        
        # Update the tenant
        updated_tenant = await tenant_manager.update_tenant(
            original_id,
            name="Updated Name",
            organization="New Org"
        )
        
        assert updated_tenant is not None
        assert updated_tenant.config.name == "Updated Name"
        assert updated_tenant.config.organization == "New Org"
        assert updated_tenant.config.contact_email == "original@test.com"  # Unchanged


@pytest.mark.asyncio
async def test_update_tenant_plan(tenant_manager):
    """Test updating tenant subscription plan."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock):
        # Create a free plan tenant
        tenant = await tenant_manager.create_tenant("Test Company", "test@test.com", TenantPlan.FREE)
        original_id = tenant.tenant_id
        
        # Upgrade to professional
        updated_tenant = await tenant_manager.update_tenant_plan(original_id, TenantPlan.PROFESSIONAL)
        
        assert updated_tenant is not None
        assert updated_tenant.config.plan == TenantPlan.PROFESSIONAL
        # Quotas should be updated for the new plan
        assert updated_tenant.quotas.javascript_enabled is True
        assert updated_tenant.quotas.proxy_enabled is True


@pytest.mark.asyncio
async def test_suspend_and_reactivate_tenant(tenant_manager):
    """Test suspending and reactivating a tenant."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock):
        # Create a tenant
        tenant = await tenant_manager.create_tenant("Test Company", "test@test.com")
        original_id = tenant.tenant_id
        
        # Suspend the tenant
        suspended_tenant = await tenant_manager.suspend_tenant(original_id, "Testing suspension")
        assert suspended_tenant is not None
        assert suspended_tenant.config.status == TenantStatus.SUSPENDED
        
        # Reactivate the tenant
        reactivated_tenant = await tenant_manager.reactivate_tenant(original_id)
        assert reactivated_tenant is not None
        assert reactivated_tenant.config.status == TenantStatus.ACTIVE


@pytest.mark.asyncio
async def test_delete_tenant(tenant_manager):
    """Test deleting a tenant."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock):
        # Create a tenant
        tenant = await tenant_manager.create_tenant("Test Company", "test@test.com")
        original_id = tenant.tenant_id
        
        # Verify tenant exists
        assert await tenant_manager.get_tenant(original_id) is not None
        
        # Delete the tenant
        success = await tenant_manager.delete_tenant(original_id)
        assert success is True
        
        # Verify tenant is no longer accessible
        assert await tenant_manager.get_tenant(original_id) is None


@pytest.mark.asyncio
async def test_api_key_management(tenant_manager):
    """Test API key registration and lookup."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock):
        # Create a tenant
        tenant = await tenant_manager.create_tenant("Test Company", "test@test.com")
        
        # Register API key
        test_api_key = "test-api-key-123"
        await tenant_manager.register_api_key(test_api_key, tenant.tenant_id)
        
        # Look up tenant by API key
        found_tenant = await tenant_manager.get_tenant_by_api_key(test_api_key)
        assert found_tenant is not None
        assert found_tenant.tenant_id == tenant.tenant_id
        
        # Unregister API key
        await tenant_manager.unregister_api_key(test_api_key)
        
        # Should not find tenant anymore
        not_found_tenant = await tenant_manager.get_tenant_by_api_key(test_api_key)
        assert not_found_tenant is None


@pytest.mark.asyncio
async def test_get_tenant_usage_stats(tenant_manager):
    """Test getting tenant usage statistics."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock):
        # Create tenants with different plans and status
        tenant1 = await tenant_manager.create_tenant("Company 1", "admin1@test.com", TenantPlan.FREE)
        tenant2 = await tenant_manager.create_tenant("Company 2", "admin2@test.com", TenantPlan.BASIC)
        await tenant_manager.suspend_tenant(tenant1.tenant_id)
        
        # Add some usage data
        tenant2.usage.requests_this_day = 100
        tenant2.usage.active_jobs = 2
        tenant2.usage.storage_used_mb = 50.5
        
        stats = await tenant_manager.get_tenant_usage_stats()
        
        assert stats["total_tenants"] == 2
        assert stats["active_tenants"] == 1
        assert stats["suspended_tenants"] == 1
        assert stats["by_plan"]["free"] == 1
        assert stats["by_plan"]["basic"] == 1
        assert stats["total_requests_today"] == 100
        assert stats["total_active_jobs"] == 2
        assert stats["total_storage_used_mb"] == 50.5


@pytest.mark.asyncio
async def test_cleanup(tenant_manager):
    """Test tenant manager cleanup."""
    with patch.object(tenant_manager, '_persist_tenants', new_callable=AsyncMock) as mock_persist:
        await tenant_manager.cleanup()
        
        # Should persist data before cleanup
        mock_persist.assert_called_once()
        
        assert len(tenant_manager._tenants) == 0
        assert len(tenant_manager._api_key_to_tenant) == 0
        assert tenant_manager._initialized is False


@pytest.mark.asyncio
async def test_background_cleanup_operations(tenant_manager):
    """Test background cleanup operations."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock), \
         patch.object(tenant_manager, '_persist_tenants', new_callable=AsyncMock):
        
        # Create a tenant
        tenant = await tenant_manager.create_tenant("Test Company", "test@test.com")
        
        # Set usage that should trigger resets
        import time
        tenant.usage.requests_this_hour = 100
        tenant.usage.hour_reset = time.time() - 3700  # Over an hour ago
        
        # Run reset operation
        await tenant_manager._reset_usage_counters()
        
        # Should have reset hourly counter
        assert tenant.usage.requests_this_hour == 0


@pytest.mark.asyncio
async def test_error_handling_in_operations(tenant_manager):
    """Test error handling in tenant operations."""
    with patch.object(tenant_manager, '_save_tenant_to_db', new_callable=AsyncMock) as mock_save:
        mock_save.side_effect = Exception("Database error")
        
        # Create tenant should still work (with warning logged)
        tenant = await tenant_manager.create_tenant("Test Company", "test@test.com")
        assert tenant is not None
        assert tenant.config.name == "Test Company"
        
        # Update should also work despite database error
        updated_tenant = await tenant_manager.update_tenant(tenant.tenant_id, name="Updated Name")
        assert updated_tenant is not None
        assert updated_tenant.config.name == "Updated Name"