# Async_Scraper API Reference

## Overview

This document provides a comprehensive reference for all Async_Scraper API endpoints, including multi-tenant operations, enhanced JavaScript features, proxy management, and administrative functions.

## Table of Contents

1. [Authentication](#authentication)
2. [Health & System Status](#health--system-status)
3. [Traditional Scraping Endpoints](#traditional-scraping-endpoints)
4. [Enhanced JavaScript Features](#enhanced-javascript-features)
5. [Job Management](#job-management)
6. [Proxy Management](#proxy-management)
7. [Multi-Tenant Admin Interface](#multi-tenant-admin-interface)
8. [Monitoring & System Management](#monitoring--system-management)
9. [WebSocket Real-time Updates](#websocket-real-time-updates)
10. [Error Responses](#error-responses)
11. [Rate Limiting](#rate-limiting)
12. [Pagination](#pagination)

## Authentication

All protected endpoints require authentication via API key in the request header.

### Headers
```
X-API-Key: your-tenant-specific-api-key
Content-Type: application/json (for POST/PUT requests)
```

### API Key Types
- **Tenant API Keys**: Access to tenant-specific scraping and job management endpoints
- **Admin API Keys**: Access to multi-tenant admin interface and system monitoring

## Health & System Status

### GET /health
Basic health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "service": "async-scraper-api",
  "version": "2.0.0",
  "timestamp": "2024-01-20T10:30:00Z"
}
```

### GET /health/detailed
Detailed system health with dependency checks (requires tenant or admin API key).

**Response:**
```json
{
  "status": "healthy",
  "service": "async-scraper-api",
  "version": "2.0.0",
  "timestamp": "2024-01-20T10:30:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "connection_pool": {
        "active": 5,
        "idle": 15,
        "total": 20
      },
      "response_time_ms": 12.5
    },
    "queue": {
      "status": "healthy",
      "depth": 23,
      "workers": {
        "active": 5,
        "total": 10
      },
      "response_time_ms": 8.2
    },
    "cache": {
      "status": "healthy",
      "l1_hit_rate": 0.85,
      "l2_hit_rate": 0.62,
      "redis_connected": true
    },
    "browser_pool": {
      "status": "healthy",
      "active_browsers": 3,
      "active_contexts": 12,
      "available_browsers": 7
    }
  },
  "metrics": {
    "active_jobs": 15,
    "total_requests_today": 1247,
    "tenant_count": 42
  }
}
```

## Traditional Scraping Endpoints

### POST /api/v1/scrape/companies
Create a company scraping job using traditional HTTP methods.

**Request Body:**
```json
{
  "companies": ["Google", "Microsoft", "OpenAI"],
  "max_emails_per_company": 10,
  "config": {
    "scraping": {
      "timeout": 30,
      "max_crawl_depth": 3,
      "respect_robots_txt": true
    },
    "proxy": {
      "enabled": true,
      "rotation_strategy": "round_robin"
    }
  }
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Created scraping job for 3 companies",
  "estimated_completion": "2024-01-20T10:35:00Z",
  "tenant_id": "tenant-123"
}
```

### POST /api/v1/scrape/domains
Create a domain crawling job using traditional HTTP methods.

**Request Body:**
```json
{
  "domains": ["example.com", "test.org"],
  "max_depth": 3,
  "max_emails_per_domain": 20,
  "config": {
    "scraping": {
      "timeout": 45,
      "respect_robots_txt": true,
      "user_agent": "AsyncScraper/2.0"
    },
    "concurrency": {
      "max_concurrent_per_domain": 5
    }
  }
}
```

**Response:**
```json
{
  "job_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "pending",
  "message": "Created domain scraping job for 2 domains",
  "estimated_completion": "2024-01-20T10:40:00Z",
  "tenant_id": "tenant-123"
}
```

## Enhanced JavaScript Features

### POST /api/v1/enhanced/scrape/companies/js
Create a JavaScript-enabled company scraping job using Playwright browsers.

**Request Body:**
```json
{
  "companies": ["OpenAI", "Stripe", "Vercel"],
  "max_emails_per_company": 15,
  "config": {
    "browser_type": "chromium",
    "headless": true,
    "take_screenshots": true,
    "viewport": {
      "width": 1920,
      "height": 1080
    },
    "wait_for_selector": ".email, [href*='mailto']",
    "wait_timeout": 10000,
    "use_proxies": true,
    "proxy_strategy": "fastest",
    "javascript_timeout": 30000
  }
}
```

**Response:**
```json
{
  "job_id": "js-770e8400-e29b-41d4-a716-446655440002",
  "status": "pending",
  "message": "Created JavaScript scraping job for 3 companies",
  "estimated_completion": "2024-01-20T10:45:00Z",
  "tenant_id": "tenant-123",
  "browser_allocated": true,
  "screenshots_enabled": true
}
```

### POST /api/v1/enhanced/scrape/domains/js
Create a JavaScript-enabled domain crawling job.

**Request Body:**
```json
{
  "domains": ["spa-example.com", "react-app.org"],
  "max_depth": 2,
  "max_emails_per_domain": 25,
  "config": {
    "browser_type": "firefox",
    "headless": false,
    "wait_for_network_idle": true,
    "network_idle_timeout": 2000,
    "block_images": false,
    "block_fonts": true,
    "use_proxies": true
  }
}
```

### POST /api/v1/enhanced/capture/screenshot
Capture screenshots of web pages.

**Request Body:**
```json
{
  "urls": ["https://example.com", "https://test.org"],
  "config": {
    "full_page": true,
    "format": "png",
    "quality": 90,
    "viewport": {
      "width": 1920,
      "height": 1080
    },
    "wait_for_selector": ".main-content",
    "delay_ms": 2000,
    "browser_type": "chromium"
  }
}
```

**Response:**
```json
{
  "job_id": "capture-880e8400-e29b-41d4-a716-446655440003",
  "status": "pending",
  "message": "Created screenshot job for 2 URLs",
  "estimated_completion": "2024-01-20T10:32:00Z",
  "output_format": "png",
  "tenant_id": "tenant-123"
}
```

### POST /api/v1/enhanced/capture/pdf
Generate PDF documents from web pages.

**Request Body:**
```json
{
  "urls": ["https://docs.example.com", "https://manual.test.org"],
  "config": {
    "format": "A4",
    "landscape": false,
    "margin": {
      "top": "1cm",
      "right": "1cm",
      "bottom": "1cm",
      "left": "1cm"
    },
    "print_background": true,
    "wait_for_selector": ".content-loaded",
    "delay_ms": 3000,
    "browser_type": "chromium"
  }
}
```

**Response:**
```json
{
  "job_id": "pdf-990e8400-e29b-41d4-a716-446655440004",
  "status": "pending",
  "message": "Created PDF generation job for 2 URLs",
  "estimated_completion": "2024-01-20T10:38:00Z",
  "output_format": "A4",
  "tenant_id": "tenant-123"
}
```

## Job Management

### GET /api/v1/jobs
List jobs for the authenticated tenant with filtering and pagination.

**Query Parameters:**
- `status` (optional): Filter by job status (`pending`, `running`, `completed`, `failed`, `cancelled`)
- `job_type` (optional): Filter by job type (`scrape_companies`, `scrape_domains`, `js_scrape_companies`, etc.)
- `created_after` (optional): ISO 8601 timestamp
- `created_before` (optional): ISO 8601 timestamp
- `skip` (optional): Number of jobs to skip (default: 0)
- `limit` (optional): Maximum number of jobs to return (default: 50, max: 100)

**Example Request:**
```
GET /api/v1/jobs?status=running&limit=10&skip=0
```

**Response:**
```json
{
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "scrape_companies",
      "status": "running",
      "created_at": "2024-01-20T10:30:00Z",
      "started_at": "2024-01-20T10:30:15Z",
      "progress": {
        "percent": 66.7,
        "current_item": "Microsoft",
        "total_items": 3,
        "completed_items": 2,
        "estimated_completion": "2024-01-20T10:34:00Z"
      },
      "tenant_id": "tenant-123"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 10,
  "tenant_id": "tenant-123"
}
```

### GET /api/v1/jobs/{job_id}
Get detailed information about a specific job.

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "js_scrape_companies",
  "status": "running",
  "created_at": "2024-01-20T10:30:00Z",
  "started_at": "2024-01-20T10:30:15Z",
  "progress": {
    "percent": 45.0,
    "current_item": "OpenAI",
    "total_items": 3,
    "completed_items": 1,
    "estimated_completion": "2024-01-20T10:38:00Z",
    "current_stage": "extracting_emails",
    "stages_completed": ["browser_setup", "page_navigation"],
    "browser_sessions": {
      "active": 1,
      "allocated": 1
    }
  },
  "config": {
    "companies": ["Google", "OpenAI", "Stripe"],
    "max_emails_per_company": 10,
    "browser_type": "chromium",
    "take_screenshots": true
  },
  "tenant_id": "tenant-123",
  "resource_usage": {
    "browser_sessions": 1,
    "proxy_requests": 15,
    "database_queries": 8
  }
}
```

### GET /api/v1/jobs/{job_id}/results
Get results for a completed job.

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "completed_at": "2024-01-20T10:34:30Z",
  "results": {
    "companies_processed": 3,
    "total_emails_found": 18,
    "emails_by_company": {
      "Google": [
        "careers@google.com",
        "support@google.com",
        "press@google.com",
        "investors@google.com"
      ],
      "OpenAI": [
        "hello@openai.com",
        "careers@openai.com",
        "support@openai.com",
        "safety@openai.com",
        "research@openai.com",
        "partnerships@openai.com"
      ],
      "Stripe": [
        "support@stripe.com",
        "sales@stripe.com",
        "careers@stripe.com",
        "press@stripe.com",
        "security@stripe.com",
        "legal@stripe.com",
        "partnerships@stripe.com",
        "developers@stripe.com"
      ]
    },
    "screenshots": {
      "Google": "https://storage.example.com/screenshots/google-20240120.png",
      "OpenAI": "https://storage.example.com/screenshots/openai-20240120.png",
      "Stripe": "https://storage.example.com/screenshots/stripe-20240120.png"
    }
  },
  "metadata": {
    "processing_time_seconds": 245.8,
    "domains_crawled": 12,
    "pages_processed": 45,
    "cache_hit_rate": 0.34,
    "proxy_requests": 67,
    "browser_sessions_used": 3,
    "screenshots_captured": 3,
    "javascript_execution_time_ms": 15420
  },
  "tenant_id": "tenant-123"
}
```

### POST /api/v1/jobs/{job_id}/cancel
Cancel a running or pending job.

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "message": "Job cancellation requested",
  "cancelled_at": "2024-01-20T10:32:15Z",
  "tenant_id": "tenant-123"
}
```

### DELETE /api/v1/jobs/{job_id}
Delete a completed, failed, or cancelled job.

**Response:**
```json
{
  "message": "Job deleted successfully",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "tenant-123"
}
```

## Proxy Management

### GET /api/v1/proxy/proxies
List all proxies for the authenticated tenant.

**Query Parameters:**
- `status` (optional): Filter by proxy status (`active`, `inactive`, `unhealthy`)
- `country` (optional): Filter by country code
- `proxy_type` (optional): Filter by proxy type (`http`, `https`, `socks5`)
- `skip` (optional): Pagination offset
- `limit` (optional): Maximum results (default: 50, max: 100)

**Response:**
```json
{
  "proxies": [
    {
      "id": "proxy-123e4567-e89b-12d3-a456-426614174000",
      "url": "http://proxy1.example.com:8080",
      "proxy_type": "http",
      "country_code": "US",
      "status": "active",
      "health": {
        "is_healthy": true,
        "last_check": "2024-01-20T10:25:00Z",
        "response_time_ms": 245.6,
        "success_rate": 0.95,
        "consecutive_failures": 0
      },
      "usage_stats": {
        "requests_today": 156,
        "requests_total": 2847,
        "last_used": "2024-01-20T10:28:00Z"
      },
      "created_at": "2024-01-15T09:00:00Z",
      "tenant_id": "tenant-123"
    }
  ],
  "total": 5,
  "skip": 0,
  "limit": 50,
  "tenant_id": "tenant-123"
}
```

### POST /api/v1/proxy/proxies
Create a new proxy configuration.

**Request Body:**
```json
{
  "url": "http://proxy.example.com:8080",
  "username": "proxy_user",
  "password": "proxy_pass",
  "proxy_type": "http",
  "country_code": "US",
  "max_concurrent_requests": 10,
  "rotation_weight": 1.0,
  "health_check_enabled": true,
  "metadata": {
    "provider": "ProxyProvider Inc",
    "location": "New York, US",
    "datacenter": "nyc-1"
  }
}
```

**Response:**
```json
{
  "id": "proxy-456e7890-e89b-12d3-a456-426614174001",
  "url": "http://proxy.example.com:8080",
  "proxy_type": "http",
  "country_code": "US",
  "status": "active",
  "created_at": "2024-01-20T10:30:00Z",
  "tenant_id": "tenant-123",
  "message": "Proxy created successfully and health check initiated"
}
```

### GET /api/v1/proxy/proxies/{proxy_id}
Get detailed information about a specific proxy.

**Response:**
```json
{
  "id": "proxy-123e4567-e89b-12d3-a456-426614174000",
  "url": "http://proxy1.example.com:8080",
  "proxy_type": "http",
  "country_code": "US",
  "status": "active",
  "health": {
    "is_healthy": true,
    "last_check": "2024-01-20T10:25:00Z",
    "response_time_ms": 245.6,
    "success_rate": 0.95,
    "consecutive_failures": 0,
    "total_checks": 288,
    "successful_checks": 274
  },
  "usage_stats": {
    "requests_today": 156,
    "requests_this_hour": 23,
    "requests_total": 2847,
    "last_used": "2024-01-20T10:28:00Z",
    "average_response_time_ms": 280.5
  },
  "configuration": {
    "max_concurrent_requests": 10,
    "rotation_weight": 1.0,
    "health_check_enabled": true,
    "timeout_seconds": 30
  },
  "metadata": {
    "provider": "ProxyProvider Inc",
    "location": "New York, US",
    "datacenter": "nyc-1"
  },
  "created_at": "2024-01-15T09:00:00Z",
  "tenant_id": "tenant-123"
}
```

### PUT /api/v1/proxy/proxies/{proxy_id}
Update proxy configuration.

**Request Body:**
```json
{
  "username": "new_user",
  "password": "new_pass",
  "max_concurrent_requests": 15,
  "rotation_weight": 1.5,
  "health_check_enabled": true,
  "metadata": {
    "location": "Los Angeles, US",
    "datacenter": "lax-1"
  }
}
```

### POST /api/v1/proxy/proxies/{proxy_id}/health-check
Manually trigger a health check for a specific proxy.

**Response:**
```json
{
  "proxy_id": "proxy-123e4567-e89b-12d3-a456-426614174000",
  "health_check_initiated": true,
  "message": "Health check started",
  "estimated_completion": "2024-01-20T10:31:00Z"
}
```

### DELETE /api/v1/proxy/proxies/{proxy_id}
Remove a proxy configuration.

**Response:**
```json
{
  "message": "Proxy deleted successfully",
  "proxy_id": "proxy-123e4567-e89b-12d3-a456-426614174000",
  "tenant_id": "tenant-123"
}
```

### GET /api/v1/proxy/stats
Get proxy system statistics for the tenant.

**Response:**
```json
{
  "tenant_id": "tenant-123",
  "proxy_stats": {
    "total_proxies": 12,
    "healthy_proxies": 10,
    "unhealthy_proxies": 2,
    "active_requests": 45,
    "requests_today": 2847,
    "average_response_time_ms": 268.4,
    "success_rate": 0.94
  },
  "rotation_strategy": "fastest",
  "by_country": {
    "US": {"total": 8, "healthy": 7},
    "EU": {"total": 3, "healthy": 2},
    "ASIA": {"total": 1, "healthy": 1}
  },
  "by_type": {
    "http": {"total": 10, "healthy": 8},
    "socks5": {"total": 2, "healthy": 2}
  }
}
```

## Multi-Tenant Admin Interface

*Note: All admin endpoints require admin API key authentication.*

### GET /admin/tenants/
List all tenants in the system.

**Query Parameters:**
- `plan` (optional): Filter by subscription plan
- `status` (optional): Filter by tenant status
- `created_after` (optional): ISO 8601 timestamp
- `skip` (optional): Pagination offset
- `limit` (optional): Maximum results

**Response:**
```json
{
  "tenants": [
    {
      "id": "tenant-123",
      "name": "Acme Corp",
      "contact_email": "admin@acme.com",
      "plan": "professional",
      "status": "active",
      "created_at": "2024-01-15T09:00:00Z",
      "api_key": "acme-api-key-***",
      "usage_stats": {
        "jobs_this_month": 156,
        "api_requests_today": 1247,
        "storage_used_mb": 2048
      },
      "quotas": {
        "max_jobs_per_hour": 100,
        "max_api_requests_per_day": 10000,
        "max_storage_mb": 10000,
        "javascript_enabled": true,
        "proxy_enabled": true,
        "webhook_enabled": true
      }
    }
  ],
  "total": 42,
  "skip": 0,
  "limit": 50
}
```

### POST /admin/tenants/
Create a new tenant.

**Request Body:**
```json
{
  "name": "New Company Inc",
  "contact_email": "admin@newcompany.com",
  "plan": "basic",
  "custom_quotas": {
    "max_jobs_per_hour": 50,
    "max_api_requests_per_day": 5000
  },
  "metadata": {
    "industry": "Technology",
    "company_size": "startup"
  }
}
```

**Response:**
```json
{
  "id": "tenant-456",
  "name": "New Company Inc",
  "contact_email": "admin@newcompany.com",
  "plan": "basic",
  "status": "active",
  "api_key": "tenant-456-generated-api-key-secure",
  "created_at": "2024-01-20T10:30:00Z",
  "quotas": {
    "max_jobs_per_hour": 50,
    "max_api_requests_per_day": 5000,
    "max_storage_mb": 5000,
    "javascript_enabled": true,
    "proxy_enabled": false,
    "webhook_enabled": false
  }
}
```

### GET /admin/tenants/{tenant_id}
Get detailed information about a specific tenant.

### PUT /admin/tenants/{tenant_id}
Update tenant configuration.

**Request Body:**
```json
{
  "plan": "professional",
  "status": "active",
  "custom_quotas": {
    "max_jobs_per_hour": 200,
    "max_api_requests_per_day": 20000
  }
}
```

### DELETE /admin/tenants/{tenant_id}
Delete a tenant and all associated data.

### POST /admin/tenants/{tenant_id}/quota
Update tenant quotas.

**Request Body:**
```json
{
  "max_jobs_per_hour": 150,
  "max_api_requests_per_day": 15000,
  "max_storage_mb": 15000,
  "javascript_enabled": true,
  "proxy_enabled": true,
  "webhook_enabled": true
}
```

### GET /admin/tenants/{tenant_id}/usage
Get detailed usage statistics for a tenant.

**Response:**
```json
{
  "tenant_id": "tenant-123",
  "current_period": {
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z",
    "jobs_created": 1247,
    "api_requests": 45678,
    "storage_used_mb": 3456,
    "browser_sessions": 234,
    "proxy_requests": 5678
  },
  "daily_stats": [
    {
      "date": "2024-01-20",
      "jobs": 45,
      "api_requests": 1247,
      "storage_mb": 123,
      "browser_sessions": 8
    }
  ],
  "quota_usage": {
    "jobs_per_hour": {
      "used": 12,
      "limit": 100,
      "percentage": 12.0
    },
    "api_requests_per_day": {
      "used": 1247,
      "limit": 10000,
      "percentage": 12.47
    },
    "storage": {
      "used_mb": 3456,
      "limit_mb": 10000,
      "percentage": 34.56
    }
  }
}
```

## Monitoring & System Management

### GET /admin/monitoring/health
Comprehensive system health check with all dependencies.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-20T10:30:00Z",
  "system_info": {
    "version": "2.0.0",
    "uptime_seconds": 86400,
    "python_version": "3.11.2",
    "memory_usage_mb": 2048,
    "cpu_usage_percent": 23.5
  },
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 12.5,
      "connection_pool": {
        "active": 15,
        "idle": 25,
        "total": 40
      }
    },
    "queue": {
      "status": "healthy",
      "depth": 156,
      "workers_active": 18,
      "workers_total": 20,
      "response_time_ms": 8.2
    },
    "cache": {
      "status": "healthy",
      "redis_connected": true,
      "l1_hit_rate": 0.85,
      "l2_hit_rate": 0.62
    },
    "browser_pool": {
      "status": "healthy",
      "active_browsers": 8,
      "active_contexts": 35,
      "available_browsers": 12
    },
    "external_connectivity": {
      "status": "healthy",
      "response_time_ms": 156.2
    }
  },
  "metrics_summary": {
    "total_tenants": 42,
    "active_jobs": 156,
    "requests_per_minute": 234,
    "error_rate": 0.02
  }
}
```

### GET /admin/monitoring/metrics
Prometheus metrics endpoint.

**Response:**
```
# HELP api_requests_total Total number of API requests
# TYPE api_requests_total counter
api_requests_total{tenant_id="tenant-123",method="POST",endpoint="/api/v1/scrape/companies",status="200"} 1247

# HELP jobs_total Total number of jobs by status
# TYPE jobs_total gauge
jobs_total{tenant_id="tenant-123",status="pending"} 23
jobs_total{tenant_id="tenant-123",status="running"} 12
jobs_total{tenant_id="tenant-123",status="completed"} 1156

# HELP browser_sessions_active Number of active browser sessions
# TYPE browser_sessions_active gauge
browser_sessions_active{tenant_id="tenant-123"} 8

# HELP proxy_requests_total Total proxy requests
# TYPE proxy_requests_total counter
proxy_requests_total{tenant_id="tenant-123",proxy_id="proxy-123",status="success"} 2847

# HELP database_connections_active Active database connections
# TYPE database_connections_active gauge
database_connections_active 15

# HELP queue_depth Current job queue depth
# TYPE queue_depth gauge
queue_depth{tenant_id="tenant-123"} 23
```

### GET /admin/monitoring/stats
Real-time system statistics.

**Response:**
```json
{
  "timestamp": "2024-01-20T10:30:00Z",
  "system": {
    "cpu_percent": 23.5,
    "memory_percent": 45.2,
    "disk_usage_percent": 67.8,
    "load_average": [1.2, 1.1, 0.9]
  },
  "api": {
    "requests_per_minute": 234,
    "average_response_time_ms": 145.6,
    "error_rate": 0.02,
    "active_connections": 45
  },
  "jobs": {
    "total_active": 156,
    "pending": 89,
    "running": 67,
    "completed_today": 1247,
    "failed_today": 23,
    "average_processing_time_minutes": 12.8
  },
  "browser_stats": {
    "active_sessions": 35,
    "total_browsers": 20,
    "contexts_per_browser": 1.75,
    "memory_usage_mb": 2048,
    "screenshots_today": 567
  },
  "proxy_stats": {
    "total_proxies": 156,
    "healthy_proxies": 142,
    "requests_today": 15678,
    "average_response_time_ms": 268.4
  },
  "database_stats": {
    "active_connections": 15,
    "idle_connections": 25,
    "total_queries_today": 45678,
    "slow_queries": 12
  },
  "queue_stats": {
    "total_depth": 234,
    "high_priority": 45,
    "normal_priority": 156,
    "low_priority": 33,
    "processing_rate_per_minute": 89
  },
  "tenant_stats": {
    "total_tenants": 42,
    "active_tenants_today": 35,
    "new_tenants_this_month": 8
  }
}
```

### POST /admin/monitoring/gc
Trigger garbage collection and cleanup operations.

**Response:**
```json
{
  "message": "Garbage collection initiated",
  "operations": [
    "memory_cleanup",
    "browser_pool_cleanup",
    "cache_cleanup",
    "job_cleanup"
  ],
  "estimated_completion": "2024-01-20T10:32:00Z"
}
```

### POST /admin/monitoring/cache-clear
Clear system caches.

**Request Body:**
```json
{
  "cache_levels": ["l1", "l2"],
  "tenant_ids": ["tenant-123", "tenant-456"]
}
```

## WebSocket Real-time Updates

### Connection
Connect to the WebSocket endpoint with API key authentication:

```
ws://localhost:8000/api/v1/ws?api_key=your-tenant-api-key
```

### Message Protocol

#### Client → Server Messages

**Subscribe to Job Updates:**
```json
{
  "action": "subscribe",
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Unsubscribe from Job Updates:**
```json
{
  "action": "unsubscribe",
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Heartbeat:**
```json
{
  "action": "ping"
}
```

#### Server → Client Messages

**Connection Acknowledgment:**
```json
{
  "type": "connection_ack",
  "message": "Connected to Async Scraper WebSocket",
  "tenant_id": "tenant-123",
  "timestamp": "2024-01-20T10:30:00Z"
}
```

**Subscription Confirmation:**
```json
{
  "type": "subscription_confirmed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Subscribed to job updates"
}
```

**Job Progress Update:**
```json
{
  "type": "job_update",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "job": {
    "status": "running",
    "progress": {
      "percent": 67.5,
      "current_item": "Microsoft",
      "total_items": 3,
      "completed_items": 2,
      "estimated_completion": "2024-01-20T10:34:00Z",
      "current_stage": "extracting_emails",
      "browser_sessions": 1
    },
    "tenant_id": "tenant-123"
  },
  "timestamp": "2024-01-20T10:32:15Z"
}
```

**Job Completion:**
```json
{
  "type": "job_completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "job": {
    "status": "completed",
    "completed_at": "2024-01-20T10:34:30Z",
    "results_summary": {
      "total_emails": 18,
      "companies_processed": 3,
      "processing_time_seconds": 245.8
    },
    "tenant_id": "tenant-123"
  },
  "timestamp": "2024-01-20T10:34:30Z"
}
```

**Error Notification:**
```json
{
  "type": "error",
  "code": "SUBSCRIPTION_ERROR",
  "message": "Job not found or access denied",
  "job_id": "invalid-job-id"
}
```

**Heartbeat Response:**
```json
{
  "type": "pong",
  "timestamp": "2024-01-20T10:30:00Z"
}
```

## Error Responses

All error responses follow a consistent format:

### Standard Error Response
```json
{
  "error": "AUTHENTICATION_FAILED",
  "message": "Invalid API key provided",
  "details": {
    "code": "AUTH_001",
    "timestamp": "2024-01-20T10:30:00Z",
    "request_id": "req_123456789"
  }
}
```

### Common Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | INVALID_REQUEST | Request validation failed |
| 401 | AUTHENTICATION_FAILED | Invalid or missing API key |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | RESOURCE_NOT_FOUND | Requested resource not found |
| 409 | CONFLICT | Resource already exists |
| 422 | VALIDATION_ERROR | Request data validation failed |
| 429 | RATE_LIMIT_EXCEEDED | Rate limit exceeded for tenant |
| 500 | INTERNAL_ERROR | Internal server error |
| 503 | SERVICE_UNAVAILABLE | Service temporarily unavailable |

### Tenant-Specific Error Codes

| Error Code | Description |
|------------|-------------|
| TENANT_QUOTA_EXCEEDED | Tenant has exceeded quota limits |
| TENANT_PLAN_RESTRICTION | Feature not available in current plan |
| TENANT_SUSPENDED | Tenant account is suspended |
| BROWSER_POOL_EXHAUSTED | No available browser sessions |
| PROXY_LIMIT_REACHED | Maximum proxy limit reached |

## Rate Limiting

### Rate Limit Headers
All responses include rate limiting information:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642680000
X-RateLimit-Retry-After: 60
```

### Rate Limit Tiers by Plan

| Plan | Requests/Hour | Requests/Day | Burst |
|------|---------------|--------------|-------|
| Free | 100 | 1,000 | 10 |
| Basic | 1,000 | 10,000 | 50 |
| Professional | 10,000 | 100,000 | 200 |
| Enterprise | 100,000 | 1,000,000 | 1,000 |

### Rate Limit Exceeded Response
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded for tenant",
  "details": {
    "limit": 1000,
    "remaining": 0,
    "reset_time": "2024-01-20T11:00:00Z",
    "retry_after": 60
  }
}
```

## Pagination

### Query Parameters
- `skip`: Number of items to skip (default: 0)
- `limit`: Maximum number of items to return (default: 50, max: 100)

### Pagination Response Format
```json
{
  "items": [...],
  "total": 1247,
  "skip": 0,
  "limit": 50,
  "has_next": true,
  "next_skip": 50
}
```

This API reference provides comprehensive documentation for all Async_Scraper endpoints, including multi-tenant features, enhanced JavaScript capabilities, proxy management, and administrative functions.