"""
Integration tests for scraping API endpoints.
"""

import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient

from scraper.api.main import create_app
from scraper.api.job_manager import get_job_manager
from scraper.api.models import JobStatus


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    """Create async test client."""
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def valid_api_key():
    """Valid API key for testing."""
    return "test-key-12345"


@pytest.fixture
def auth_headers(valid_api_key):
    """Authentication headers."""
    return {"X-API-Key": valid_api_key}


class TestScrapeEndpoints:
    """Test scraping API endpoints."""

    @pytest.mark.asyncio
    async def test_scrape_companies_success(self, async_client, auth_headers):
        """Test successful company scraping job creation."""
        request_data = {
            "companies": ["Google", "Microsoft", "Apple"],
            "max_emails_per_company": 5,
            "include_subdomains": True,
            "verify_emails": False
        }
        
        response = await async_client.post(
            "/api/v1/scrape/companies",
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "Created scraping job for 3 companies" in data["message"]
        assert "estimated_duration" in data

    @pytest.mark.asyncio
    async def test_scrape_companies_validation_error(self, async_client, auth_headers):
        """Test validation error for empty companies list."""
        request_data = {
            "companies": [],  # Empty list should fail validation
            "max_emails_per_company": 5
        }
        
        response = await async_client.post(
            "/api/v1/scrape/companies", 
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_scrape_companies_unauthorized(self, async_client):
        """Test unauthorized access to companies endpoint."""
        request_data = {
            "companies": ["Google"],
            "max_emails_per_company": 5
        }
        
        response = await async_client.post(
            "/api/v1/scrape/companies",
            json=request_data
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_scrape_domains_success(self, async_client, auth_headers):
        """Test successful domain scraping job creation."""
        request_data = {
            "domains": ["google.com", "microsoft.com"],
            "max_emails_per_domain": 10,
            "crawl_depth": 2,
            "verify_emails": True
        }
        
        response = await async_client.post(
            "/api/v1/scrape/domains",
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "Created scraping job for 2 domains" in data["message"]
        assert "estimated_duration" in data

    @pytest.mark.asyncio
    async def test_scrape_domains_with_custom_config(self, async_client, auth_headers):
        """Test domain scraping with custom configuration."""
        request_data = {
            "domains": ["example.com"],
            "max_emails_per_domain": 15,
            "crawl_depth": 3,
            "timeout": 60,
            "custom_config": {
                "user_agent": "Custom Bot",
                "delay": 2
            }
        }
        
        response = await async_client.post(
            "/api/v1/scrape/domains",
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    @pytest.mark.asyncio
    async def test_scrape_domains_validation_limits(self, async_client, auth_headers):
        """Test validation limits for domain scraping."""
        request_data = {
            "domains": ["test.com"],
            "max_emails_per_domain": 150,  # Above limit
            "crawl_depth": 10  # Above limit
        }
        
        response = await async_client.post(
            "/api/v1/scrape/domains",
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422


class TestJobsEndpoints:
    """Test job management API endpoints."""

    @pytest.mark.asyncio
    async def test_list_jobs(self, async_client, auth_headers):
        """Test listing jobs."""
        response = await async_client.get(
            "/api/v1/jobs",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, async_client, auth_headers):
        """Test listing jobs with status filter."""
        response = await async_client.get(
            "/api/v1/jobs?status=pending&limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, async_client, auth_headers):
        """Test getting non-existent job."""
        response = await async_client.get(
            "/api/v1/jobs/non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_complete_job_workflow(self, async_client, auth_headers):
        """Test complete job workflow: create, get, results, cancel."""
        # Create a job
        request_data = {
            "companies": ["TestCorp"],
            "max_emails_per_company": 3
        }
        
        create_response = await async_client.post(
            "/api/v1/scrape/companies",
            json=request_data,
            headers=auth_headers
        )
        
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]
        
        # Get job details (should be running or pending)
        await asyncio.sleep(0.05)  # Small delay to let job start
        job_response = await async_client.get(
            f"/api/v1/jobs/{job_id}",
            headers=auth_headers
        )
        
        assert job_response.status_code == 200
        job_data = job_response.json()
        assert job_data["id"] == job_id
        assert job_data["type"] == "scrape_companies"
        
        # Try to get results (should fail for non-completed job)
        results_response = await async_client.get(
            f"/api/v1/jobs/{job_id}/results",
            headers=auth_headers
        )
        
        # If job hasn't completed yet, this should fail
        if job_data["status"] != "completed":
            assert results_response.status_code == 400
            assert "not completed" in results_response.json()["detail"]
        
        # Cancel the job
        cancel_response = await async_client.post(
            f"/api/v1/jobs/{job_id}/cancel",
            headers=auth_headers
        )
        
        assert cancel_response.status_code == 200
        assert "cancelled" in cancel_response.json()["message"]
        
        # Verify job is cancelled
        updated_job_response = await async_client.get(
            f"/api/v1/jobs/{job_id}",
            headers=auth_headers
        )
        
        assert updated_job_response.status_code == 200
        assert updated_job_response.json()["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_completed_job(self, async_client, auth_headers):
        """Test cancelling a completed job (should fail)."""
        # For this test, we need to create a job and simulate completion
        job_manager = get_job_manager()
        
        # Create job directly in manager
        from scraper.api.models import JobType
        job = job_manager.create_job(JobType.SCRAPE_COMPANIES, {"companies": ["test"]})
        job_manager.update_job_status(job.id, JobStatus.COMPLETED)
        
        # Try to cancel completed job
        response = await async_client.post(
            f"/api/v1/jobs/{job.id}/cancel",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Cannot cancel job in status" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_job(self, async_client, auth_headers):
        """Test deleting a completed job."""
        # Create and complete a job
        job_manager = get_job_manager()
        
        from scraper.api.models import JobType
        job = job_manager.create_job(JobType.SCRAPE_COMPANIES, {"companies": ["test"]})
        job_manager.update_job_status(job.id, JobStatus.COMPLETED)
        
        # Delete the job
        response = await async_client.delete(
            f"/api/v1/jobs/{job.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "deleted" in response.json()["message"]
        
        # Verify job is gone
        get_response = await async_client.get(
            f"/api/v1/jobs/{job.id}",
            headers=auth_headers
        )
        
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_running_job(self, async_client, auth_headers):
        """Test deleting a running job (should fail)."""
        job_manager = get_job_manager()
        
        from scraper.api.models import JobType
        job = job_manager.create_job(JobType.SCRAPE_COMPANIES, {"companies": ["test"]})
        job_manager.update_job_status(job.id, JobStatus.RUNNING)
        
        # Try to delete running job
        response = await async_client.delete(
            f"/api/v1/jobs/{job.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Cannot delete job in status" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_jobs_unauthorized(self, async_client):
        """Test unauthorized access to jobs endpoints."""
        # Test list jobs
        response = await async_client.get("/api/v1/jobs")
        assert response.status_code == 401
        
        # Test get job
        response = await async_client.get("/api/v1/jobs/test-id")
        assert response.status_code == 401
        
        # Test cancel job
        response = await async_client.post("/api/v1/jobs/test-id/cancel")
        assert response.status_code == 401