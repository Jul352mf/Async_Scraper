"""Tests for tenant models and functionality."""

import pytest
from datetime import datetime
from scraper.core.tenant.models import (
    TenantModel, TenantConfig, TenantStatus, TenantPlan, 
    TenantQuotas, TenantUsage
)


@pytest.fixture
def sample_tenant():
    """Create a sample tenant for testing."""
    return TenantModel.create_new(
        name="Test Tenant",
        contact_email="test@example.com",
        plan=TenantPlan.BASIC
    )


def test_create_new_tenant():
    """Test creating a new tenant."""
    tenant = TenantModel.create_new(
        name="Test Company",
        contact_email="admin@testcompany.com",
        plan=TenantPlan.PROFESSIONAL
    )
    
    assert tenant.config.name == "Test Company"
    assert tenant.config.contact_email == "admin@testcompany.com"
    assert tenant.config.plan == TenantPlan.PROFESSIONAL
    assert tenant.config.status == TenantStatus.ACTIVE
    assert tenant.tenant_id is not None
    assert len(tenant.tenant_id) == 36  # UUID length


def test_tenant_quotas_by_plan():
    """Test that quotas are set correctly based on plan."""
    # Free plan
    free_tenant = TenantModel.create_new("Free", "free@test.com", TenantPlan.FREE)
    assert free_tenant.quotas.requests_per_hour == 100
    assert free_tenant.quotas.concurrent_jobs == 2
    assert free_tenant.quotas.javascript_enabled is False
    assert free_tenant.quotas.proxy_enabled is False
    
    # Basic plan
    basic_tenant = TenantModel.create_new("Basic", "basic@test.com", TenantPlan.BASIC)
    assert basic_tenant.quotas.requests_per_hour == 1000
    assert basic_tenant.quotas.concurrent_jobs == 5
    assert basic_tenant.quotas.javascript_enabled is True
    assert basic_tenant.quotas.proxy_enabled is False
    
    # Professional plan
    pro_tenant = TenantModel.create_new("Pro", "pro@test.com", TenantPlan.PROFESSIONAL)
    assert pro_tenant.quotas.requests_per_hour == 5000
    assert pro_tenant.quotas.concurrent_jobs == 20
    assert pro_tenant.quotas.javascript_enabled is True
    assert pro_tenant.quotas.proxy_enabled is True
    
    # Enterprise plan
    enterprise_tenant = TenantModel.create_new("Enterprise", "enterprise@test.com", TenantPlan.ENTERPRISE)
    assert enterprise_tenant.quotas.requests_per_hour == 25000
    assert enterprise_tenant.quotas.concurrent_jobs == 100
    assert enterprise_tenant.quotas.webhook_enabled is True


def test_tenant_is_active(sample_tenant):
    """Test tenant active status check."""
    assert sample_tenant.is_active() is True
    
    sample_tenant.config.status = TenantStatus.SUSPENDED
    assert sample_tenant.is_active() is False


def test_can_make_request(sample_tenant):
    """Test request quota checking."""
    # Should be able to make requests initially
    assert sample_tenant.can_make_request() is True
    
    # Exceed hourly quota
    sample_tenant.usage.requests_this_hour = sample_tenant.quotas.requests_per_hour + 1
    assert sample_tenant.can_make_request() is False
    
    # Reset and test daily quota
    sample_tenant.usage.requests_this_hour = 0
    sample_tenant.usage.requests_this_day = sample_tenant.quotas.requests_per_day + 1
    assert sample_tenant.can_make_request() is False
    
    # Test inactive tenant
    sample_tenant.usage.requests_this_day = 0
    sample_tenant.config.status = TenantStatus.SUSPENDED
    assert sample_tenant.can_make_request() is False


def test_can_create_job(sample_tenant):
    """Test job creation quota checking."""
    # Should be able to create jobs initially
    assert sample_tenant.can_create_job() is True
    
    # Exceed concurrent jobs quota
    sample_tenant.usage.active_jobs = sample_tenant.quotas.concurrent_jobs + 1
    assert sample_tenant.can_create_job() is False
    
    # Reset and test daily jobs quota
    sample_tenant.usage.active_jobs = 0
    sample_tenant.usage.jobs_this_day = sample_tenant.quotas.max_jobs_per_day + 1
    assert sample_tenant.can_create_job() is False


def test_has_feature(sample_tenant):
    """Test feature access checking."""
    # Basic plan should have JavaScript but not proxy
    assert sample_tenant.has_feature("javascript") is True
    assert sample_tenant.has_feature("proxy") is False
    assert sample_tenant.has_feature("custom_headers") is True
    assert sample_tenant.has_feature("webhook") is False
    
    # Unknown feature should return False
    assert sample_tenant.has_feature("unknown_feature") is False


def test_record_request(sample_tenant):
    """Test request recording and counter resets."""
    initial_hour = sample_tenant.usage.requests_this_hour
    initial_day = sample_tenant.usage.requests_this_day
    initial_month = sample_tenant.usage.requests_this_month
    
    sample_tenant.record_request()
    
    assert sample_tenant.usage.requests_this_hour == initial_hour + 1
    assert sample_tenant.usage.requests_this_day == initial_day + 1
    assert sample_tenant.usage.requests_this_month == initial_month + 1
    assert sample_tenant.config.last_activity is not None


def test_record_job_lifecycle(sample_tenant):
    """Test job lifecycle recording."""
    initial_active = sample_tenant.usage.active_jobs
    initial_day = sample_tenant.usage.jobs_this_day
    initial_total = sample_tenant.usage.total_jobs
    
    # Start job
    sample_tenant.record_job_start()
    assert sample_tenant.usage.active_jobs == initial_active + 1
    assert sample_tenant.usage.jobs_this_day == initial_day + 1
    assert sample_tenant.usage.total_jobs == initial_total + 1
    
    # End job
    sample_tenant.record_job_end()
    assert sample_tenant.usage.active_jobs == initial_active  # Back to original


def test_get_usage_percentage(sample_tenant):
    """Test usage percentage calculation."""
    # Set some usage
    sample_tenant.usage.requests_this_hour = 50
    sample_tenant.usage.active_jobs = 2
    sample_tenant.usage.storage_used_mb = 100
    
    percentages = sample_tenant.get_usage_percentage()
    
    # Basic plan: 1000 requests/hour, 5 concurrent jobs, 1000MB storage
    assert percentages["requests_hour"] == 5.0  # 50/1000 * 100
    assert percentages["concurrent_jobs"] == 40.0  # 2/5 * 100
    assert percentages["storage"] == 10.0  # 100/1000 * 100


def test_to_dict_and_from_dict(sample_tenant):
    """Test tenant serialization and deserialization."""
    # Convert to dict
    data = sample_tenant.to_dict()
    
    assert "tenant_id" in data
    assert "config" in data
    assert "quotas" in data
    assert "usage" in data
    assert "usage_percentage" in data
    
    # Convert back from dict
    restored_tenant = TenantModel.from_dict(data)
    
    assert restored_tenant.tenant_id == sample_tenant.tenant_id
    assert restored_tenant.config.name == sample_tenant.config.name
    assert restored_tenant.config.contact_email == sample_tenant.config.contact_email
    assert restored_tenant.quotas.requests_per_hour == sample_tenant.quotas.requests_per_hour
    assert restored_tenant.usage.requests_this_hour == sample_tenant.usage.requests_this_hour


def test_tenant_config_validation():
    """Test tenant configuration validation."""
    # Valid config
    config = TenantConfig(
        tenant_id="test-123",
        name="Test Tenant",
        contact_email="test@example.com"
    )
    
    assert config.tenant_id == "test-123"
    assert config.name == "Test Tenant"
    assert config.status == TenantStatus.ACTIVE
    assert config.plan == TenantPlan.FREE


def test_tenant_usage_counter_resets():
    """Test usage counter reset logic."""
    import time
    
    usage = TenantUsage()
    current_time = time.time()
    
    # Set counters and reset times
    usage.requests_this_hour = 100
    usage.requests_this_day = 500
    usage.hour_reset = current_time - 3700  # Over 1 hour ago
    usage.day_reset = current_time - 90000   # Over 1 day ago
    
    # Create tenant with this usage
    tenant = TenantModel("test", TenantConfig(tenant_id="test", name="Test", contact_email="test@test.com"), usage=usage)
    
    # Record a request (which should trigger resets)
    tenant.record_request()
    
    # Hour counter should be reset
    assert tenant.usage.requests_this_hour == 1  # Just the new request
    # Day counter should be reset  
    assert tenant.usage.requests_this_day == 1   # Just the new request