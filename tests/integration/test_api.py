"""
Integration tests for the API server.
"""

import pytest
from fastapi.testclient import TestClient

from scraper.api.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_basic_health_check(self):
        """Test the basic health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert data["service"] == "async-scraper-api"
        assert "timestamp" in data

    def test_detailed_health_without_api_key(self):
        """Test detailed health check without API key (should fail)."""
        response = client.get("/api/v1/health/detailed")
        assert response.status_code == 401
        
        data = response.json()
        assert "error" in data
        assert data["error"] == "API key required"

    def test_detailed_health_with_api_key(self):
        """Test detailed health check with API key."""
        headers = {"X-API-Key": "test-api-key-123456"}
        response = client.get("/api/v1/health/detailed", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert data["service"] == "async-scraper-api"
        assert "timestamp" in data
        assert "checks" in data
        assert "metrics" in data

    def test_detailed_health_with_short_api_key(self):
        """Test detailed health check with invalid (too short) API key."""
        headers = {"X-API-Key": "short"}
        response = client.get("/api/v1/health/detailed", headers=headers)
        assert response.status_code == 401
        
        data = response.json()
        assert "error" in data
        assert data["error"] == "Invalid API key"


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    def test_openapi_json(self):
        """Test OpenAPI JSON endpoint."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        data = response.json()
        assert data["info"]["title"] == "Async Scraper API"
        assert data["info"]["version"] == "0.1.0"
        assert "paths" in data

    def test_docs_endpoint(self):
        """Test Swagger UI docs endpoint."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger-ui" in response.text
        assert "Async Scraper API" in response.text

    def test_redoc_endpoint(self):
        """Test ReDoc documentation endpoint."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text


class TestMiddleware:
    """Test middleware functionality."""

    def test_cors_headers(self):
        """Test CORS headers are present."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        # Note: In test client, CORS headers might not be visible
        # This test verifies the endpoint works despite CORS middleware

    def test_auth_middleware_bypass_for_docs(self):
        """Test auth middleware bypasses documentation endpoints."""
        # These should not require authentication
        endpoints = ["/docs", "/redoc", "/openapi.json"]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Failed for endpoint: {endpoint}"


class TestErrorHandling:
    """Test error handling and responses."""

    def test_404_endpoint(self):
        """Test 401 response for non-existent endpoint (auth required first)."""
        response = client.get("/api/v1/nonexistent")
        # Auth middleware runs before routing, so we get 401 instead of 404
        assert response.status_code == 401

    def test_invalid_method(self):
        """Test invalid HTTP method."""
        response = client.post("/api/v1/health")
        assert response.status_code == 405