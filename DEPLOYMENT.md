# Async_Scraper Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying Async_Scraper in various environments, from development to enterprise production with multi-tenancy support.

## Table of Contents

1. [Quick Development Setup](#quick-development-setup)
2. [Production Environment](#production-environment)
3. [Multi-Tenant SaaS Deployment](#multi-tenant-saas-deployment)
4. [Infrastructure Requirements](#infrastructure-requirements)
5. [Configuration Management](#configuration-management)
6. [Monitoring & Observability](#monitoring--observability)
7. [Security Considerations](#security-considerations)
8. [Scaling & Performance](#scaling--performance)
9. [Backup & Recovery](#backup--recovery)
10. [Troubleshooting](#troubleshooting)

## Quick Development Setup

### Local Development with SQLite

```bash
# Clone and install
git clone https://github.com/Jul352mf/Async_Scraper.git
cd Async_Scraper
pip install -e ".[dev]"

# Basic configuration for development
export SCRAPER_DEBUG=true
export SCRAPER_DATABASE_USE_SQLITE=true
export SCRAPER_DATABASE_SQLITE_PATH="./dev.db"
export SCRAPER_QUEUE_USE_REDIS=false
export SCRAPER_MULTI_TENANCY_ENABLED=false

# Start the development server
async-scraper api --host 0.0.0.0 --port 8000
```

### Development with Docker Compose

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  async-scraper:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SCRAPER_DEBUG=true
      - SCRAPER_DATABASE_USE_SQLITE=true
      - SCRAPER_QUEUE_USE_REDIS=false
      - SCRAPER_API_API_KEYS=dev-key-123456
    volumes:
      - ./scraper:/app/scraper
      - ./tests:/app/tests
    command: ["async-scraper", "api", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d
```

## Production Environment

### Infrastructure Stack

#### Core Services
- **Application Server**: Python 3.11+ with uvicorn/gunicorn
- **Database**: PostgreSQL 13+ for data persistence
- **Queue**: Redis 6+ for distributed job processing
- **Load Balancer**: Nginx or HAProxy for request distribution
- **Process Manager**: systemd or supervisor for service management

#### Monitoring Stack
- **Metrics**: Prometheus for metrics collection
- **Visualization**: Grafana for dashboards
- **Tracing**: Jaeger or Zipkin for distributed tracing
- **Logging**: ELK Stack or similar for log aggregation

### Production Docker Setup

```dockerfile
# Dockerfile.prod
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxss1 \
    libgtk-3-0 \
    libxshmfence1 \
    libasound2

WORKDIR /app

# Copy requirements and install dependencies
COPY pyproject.toml .
RUN pip install -e .

# Install Playwright browsers
RUN python -m playwright install chromium

# Copy application
COPY scraper/ ./scraper/
COPY tests/ ./tests/

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["gunicorn", "scraper.api.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: async_scraper
      POSTGRES_USER: scraper_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U scraper_user -d async_scraper"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  async-scraper:
    build: 
      context: .
      dockerfile: Dockerfile.prod
    ports:
      - "8000:8000"
    environment:
      - SCRAPER_DATABASE_USE_SQLITE=false
      - SCRAPER_DATABASE_HOST=postgres
      - SCRAPER_DATABASE_PORT=5432
      - SCRAPER_DATABASE_DATABASE=async_scraper
      - SCRAPER_DATABASE_USER=scraper_user
      - SCRAPER_DATABASE_PASSWORD=${POSTGRES_PASSWORD}
      - SCRAPER_QUEUE_USE_REDIS=true
      - SCRAPER_QUEUE_REDIS_URL=redis://redis:6379/1
      - SCRAPER_API_API_KEYS=${API_KEYS}
      - SCRAPER_MONITORING_PROMETHEUS_ENABLED=true
      - SCRAPER_MULTI_TENANCY_ENABLED=true
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl/certs
    depends_on:
      - async-scraper
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

### Nginx Configuration

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream async_scraper {
        server async-scraper:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $http_x_api_key zone=tenant:10m rate=100r/s;

    server {
        listen 80;
        server_name yourdomain.com;
        
        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com;

        ssl_certificate /etc/ssl/certs/cert.pem;
        ssl_certificate_key /etc/ssl/certs/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";

        # API endpoints
        location /api/ {
            limit_req zone=tenant burst=20 nodelay;
            proxy_pass http://async_scraper;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_read_timeout 86400;
        }

        # Admin endpoints (restricted access)
        location /admin/ {
            limit_req zone=api burst=10 nodelay;
            # IP whitelist for admin access
            allow 10.0.0.0/8;
            allow 172.16.0.0/12;
            allow 192.168.0.0/16;
            deny all;
            
            proxy_pass http://async_scraper;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health checks
        location /health {
            proxy_pass http://async_scraper;
            access_log off;
        }

        # Metrics (restrict access)
        location /metrics {
            allow 10.0.0.0/8;
            deny all;
            proxy_pass http://async_scraper;
        }
    }
}
```

## Multi-Tenant SaaS Deployment

### Environment Configuration for Multi-Tenancy

```bash
# Multi-tenant production configuration
export SCRAPER_MULTI_TENANCY_ENABLED=true
export SCRAPER_MULTI_TENANCY_DEFAULT_PLAN=free
export SCRAPER_MULTI_TENANCY_ENFORCE_QUOTAS=true

# Admin API keys for tenant management
export SCRAPER_ADMIN_API_KEYS="admin-super-key-secure-random-string"

# Database with tenant isolation
export SCRAPER_DATABASE_USE_SQLITE=false
export SCRAPER_DATABASE_HOST=postgres-cluster.example.com
export SCRAPER_DATABASE_PORT=5432
export SCRAPER_DATABASE_DATABASE=async_scraper_prod
export SCRAPER_DATABASE_USER=scraper_prod_user
export SCRAPER_DATABASE_PASSWORD=secure-database-password

# Redis cluster for distributed processing
export SCRAPER_QUEUE_USE_REDIS=true
export SCRAPER_QUEUE_REDIS_URL=redis://redis-cluster.example.com:6379/1
export SCRAPER_QUEUE_MAX_WORKERS=20

# Enhanced monitoring for multi-tenant operations
export SCRAPER_MONITORING_PROMETHEUS_ENABLED=true
export SCRAPER_MONITORING_TRACING_ENABLED=true
export SCRAPER_MONITORING_HEALTH_CHECK_INTERVAL=30

# Proxy management for tenant isolation
export SCRAPER_PROXY_ENABLED=true
export SCRAPER_PROXY_ROTATION_STRATEGY=geographic
```

### Tenant Provisioning Script

```bash
#!/bin/bash
# create-tenant.sh - Automated tenant creation

ADMIN_KEY="admin-super-key-secure-random-string"
API_BASE="https://api.yourdomain.com"

if [ $# -ne 3 ]; then
    echo "Usage: $0 <tenant_name> <contact_email> <plan>"
    echo "Plans: free, basic, professional, enterprise"
    exit 1
fi

TENANT_NAME="$1"
CONTACT_EMAIL="$2"
PLAN="$3"

# Create tenant
RESPONSE=$(curl -s -X POST "${API_BASE}/admin/tenants/" \
    -H "X-API-Key: ${ADMIN_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"${TENANT_NAME}\",
        \"contact_email\": \"${CONTACT_EMAIL}\",
        \"plan\": \"${PLAN}\"
    }")

# Extract tenant ID and API key
TENANT_ID=$(echo "$RESPONSE" | jq -r '.id')
API_KEY=$(echo "$RESPONSE" | jq -r '.api_key')

echo "✅ Tenant created successfully!"
echo "Tenant ID: ${TENANT_ID}"
echo "API Key: ${API_KEY}"
echo "Plan: ${PLAN}"

# Send welcome email (implement your email service integration)
echo "📧 Sending welcome email to ${CONTACT_EMAIL}..."
```

## Infrastructure Requirements

### System Requirements

#### Minimum Requirements (Development)
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 10GB SSD
- **Network**: 10 Mbps

#### Recommended Production (Single Instance)
- **CPU**: 4-8 cores
- **RAM**: 16-32GB
- **Storage**: 100GB+ SSD
- **Network**: 100 Mbps+

#### Enterprise Multi-Tenant (High Availability)
- **Load Balancer**: 2+ instances (2 cores, 4GB RAM each)
- **Application Servers**: 3+ instances (8 cores, 32GB RAM each)
- **Database**: PostgreSQL cluster (16 cores, 64GB RAM per node)
- **Redis**: Cluster setup (4 cores, 16GB RAM per node)
- **Storage**: 1TB+ SSD with backup

### Cloud Provider Recommendations

#### AWS Deployment
```yaml
# AWS ECS Task Definition example
family: async-scraper
networkMode: awsvpc
requiresCompatibilities:
  - FARGATE
cpu: '2048'
memory: '4096'
executionRoleArn: arn:aws:iam::account:role/ecsTaskExecutionRole
taskRoleArn: arn:aws:iam::account:role/ecsTaskRole

containerDefinitions:
  - name: async-scraper
    image: your-registry/async-scraper:latest
    portMappings:
      - containerPort: 8000
        protocol: tcp
    environment:
      - name: SCRAPER_DATABASE_HOST
        value: your-rds-endpoint.amazonaws.com
      - name: SCRAPER_QUEUE_REDIS_URL
        value: your-elasticache-endpoint:6379
    secrets:
      - name: SCRAPER_DATABASE_PASSWORD
        valueFrom: arn:aws:secretsmanager:region:account:secret:db-password
      - name: SCRAPER_API_API_KEYS
        valueFrom: arn:aws:secretsmanager:region:account:secret:api-keys
    logConfiguration:
      logDriver: awslogs
      options:
        awslogs-group: /ecs/async-scraper
        awslogs-region: us-west-2
        awslogs-stream-prefix: ecs
```

#### Google Cloud Run
```yaml
# cloudrun.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: async-scraper
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/execution-environment: gen2
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containerConcurrency: 100
      containers:
      - image: gcr.io/your-project/async-scraper:latest
        ports:
        - containerPort: 8000
        resources:
          limits:
            cpu: 2000m
            memory: 4Gi
        env:
        - name: SCRAPER_DATABASE_HOST
          value: your-cloud-sql-ip
        - name: SCRAPER_QUEUE_REDIS_URL
          value: redis://your-memorystore-ip:6379
        - name: SCRAPER_DATABASE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secrets
              key: password
```

## Configuration Management

### Environment-Specific Configurations

#### Development Configuration
```json
{
  "debug": true,
  "cache": {
    "l1_enabled": true,
    "l2_enabled": false,
    "l3_enabled": true
  },
  "database": {
    "use_sqlite": true,
    "sqlite_path": "./dev.db",
    "auto_migrate": true
  },
  "queue": {
    "use_redis": false,
    "max_workers": 2
  },
  "browser": {
    "max_browsers": 2,
    "headless": true
  },
  "multi_tenancy": {
    "enabled": false
  },
  "monitoring": {
    "prometheus_enabled": false
  }
}
```

#### Staging Configuration
```json
{
  "debug": false,
  "cache": {
    "l1_enabled": true,
    "l2_enabled": true,
    "l2_redis_url": "redis://staging-redis:6379",
    "l3_enabled": true
  },
  "database": {
    "use_sqlite": false,
    "host": "staging-postgres",
    "port": 5432,
    "database": "async_scraper_staging",
    "auto_migrate": true
  },
  "queue": {
    "use_redis": true,
    "redis_url": "redis://staging-redis:6379/1",
    "max_workers": 5
  },
  "multi_tenancy": {
    "enabled": true,
    "enforce_quotas": false
  },
  "monitoring": {
    "prometheus_enabled": true,
    "tracing_enabled": false
  }
}
```

#### Production Configuration
```json
{
  "debug": false,
  "cache": {
    "l1_enabled": true,
    "l1_max_size": 10000,
    "l2_enabled": true,
    "l2_redis_url": "redis://prod-redis-cluster:6379",
    "l3_enabled": true
  },
  "database": {
    "use_sqlite": false,
    "host": "prod-postgres-primary",
    "port": 5432,
    "database": "async_scraper_prod",
    "connection_pool_size": 20,
    "auto_migrate": false
  },
  "queue": {
    "use_redis": true,
    "redis_url": "redis://prod-redis-cluster:6379/1",
    "max_workers": 20,
    "health_check_interval": 30
  },
  "browser": {
    "max_browsers": 10,
    "max_contexts_per_browser": 20,
    "headless": true,
    "timeout": 120
  },
  "proxy": {
    "enabled": true,
    "rotation_strategy": "fastest",
    "health_check_interval": 300
  },
  "multi_tenancy": {
    "enabled": true,
    "enforce_quotas": true,
    "default_plan": "basic"
  },
  "monitoring": {
    "prometheus_enabled": true,
    "tracing_enabled": true,
    "health_check_interval": 30
  },
  "api": {
    "rate_limit_per_minute": 1000,
    "cors_origins": ["https://yourdomain.com"],
    "docs_enabled": false
  }
}
```

### Secret Management

#### Using HashiCorp Vault
```bash
# Store secrets in Vault
vault kv put secret/async-scraper/prod \
    database_password="secure-db-password" \
    api_keys="key1,key2,key3" \
    admin_api_keys="admin-key-1,admin-key-2"

# Retrieve in application startup
export SCRAPER_DATABASE_PASSWORD=$(vault kv get -field=database_password secret/async-scraper/prod)
export SCRAPER_API_API_KEYS=$(vault kv get -field=api_keys secret/async-scraper/prod)
```

#### Using Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: async-scraper-secrets
type: Opaque
stringData:
  database-password: "secure-db-password"
  api-keys: "key1,key2,key3"
  admin-api-keys: "admin-key-1,admin-key-2"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: async-scraper
spec:
  replicas: 3
  selector:
    matchLabels:
      app: async-scraper
  template:
    metadata:
      labels:
        app: async-scraper
    spec:
      containers:
      - name: async-scraper
        image: async-scraper:latest
        env:
        - name: SCRAPER_DATABASE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: async-scraper-secrets
              key: database-password
        - name: SCRAPER_API_API_KEYS
          valueFrom:
            secretKeyRef:
              name: async-scraper-secrets
              key: api-keys
```

## Monitoring & Observability

### Prometheus Metrics Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'async-scraper'
    static_configs:
      - targets: ['async-scraper:8000']
    metrics_path: '/admin/monitoring/metrics'
    scrape_interval: 30s
    bearer_token: 'admin-metrics-token'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "id": null,
    "title": "Async Scraper - Multi-Tenant Dashboard",
    "tags": ["async-scraper", "multi-tenant"],
    "timezone": "browser",
    "panels": [
      {
        "title": "API Requests by Tenant",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(api_requests_total[5m])",
            "legendFormat": "{{tenant_id}} - {{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Job Processing by Status",
        "type": "stat",
        "targets": [
          {
            "expr": "sum by (status) (jobs_total)",
            "legendFormat": "{{status}}"
          }
        ]
      },
      {
        "title": "Browser Sessions Active",
        "type": "graph",
        "targets": [
          {
            "expr": "browser_sessions_active",
            "legendFormat": "Active Sessions"
          }
        ]
      },
      {
        "title": "Proxy Health Status",
        "type": "stat",
        "targets": [
          {
            "expr": "proxy_health_status",
            "legendFormat": "{{proxy_id}}"
          }
        ]
      },
      {
        "title": "Database Connections",
        "type": "graph",
        "targets": [
          {
            "expr": "database_connections_active",
            "legendFormat": "Active Connections"
          }
        ]
      },
      {
        "title": "Queue Depth by Tenant",
        "type": "graph",
        "targets": [
          {
            "expr": "queue_depth",
            "legendFormat": "{{tenant_id}}"
          }
        ]
      }
    ]
  }
}
```

### Health Check Configuration

```yaml
# Docker Compose health checks
healthcheck:
  test: |
    curl -f http://localhost:8000/admin/monitoring/health \
    -H "X-API-Key: $${ADMIN_API_KEY}" || exit 1
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Log Aggregation with ELK Stack

```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.15.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"

  logstash:
    image: docker.elastic.co/logstash/logstash:7.15.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:7.15.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch

volumes:
  elasticsearch_data:
```

```ruby
# logstash.conf
input {
  beats {
    port => 5044
  }
}

filter {
  if [fields][service] == "async-scraper" {
    json {
      source => "message"
    }
    
    if [tenant_id] {
      mutate {
        add_tag => [ "multi-tenant" ]
      }
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "async-scraper-%{+YYYY.MM.dd}"
  }
}
```

## Security Considerations

### Network Security

```bash
# Firewall configuration (iptables example)
# Allow only necessary ports
iptables -A INPUT -p tcp --dport 22 -j ACCEPT    # SSH
iptables -A INPUT -p tcp --dport 80 -j ACCEPT    # HTTP
iptables -A INPUT -p tcp --dport 443 -j ACCEPT   # HTTPS
iptables -A INPUT -p tcp --dport 5432 -s 10.0.0.0/8 -j ACCEPT  # PostgreSQL (internal)
iptables -A INPUT -p tcp --dport 6379 -s 10.0.0.0/8 -j ACCEPT  # Redis (internal)
iptables -A INPUT -j DROP  # Drop all other traffic
```

### SSL/TLS Configuration

```bash
# Generate SSL certificate with Let's Encrypt
certbot certonly --webroot \
    -w /var/www/html \
    -d api.yourdomain.com \
    -d admin.yourdomain.com \
    --email admin@yourdomain.com \
    --agree-tos \
    --no-eff-email

# Auto-renewal
echo "0 12 * * * /usr/bin/certbot renew --quiet" | crontab -
```

### Database Security

```sql
-- Create dedicated database user with minimal privileges
CREATE USER scraper_app WITH PASSWORD 'secure-password';
GRANT CONNECT ON DATABASE async_scraper TO scraper_app;
GRANT USAGE ON SCHEMA public TO scraper_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO scraper_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO scraper_app;

-- Enable row-level security for tenant isolation
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON jobs USING (tenant_id = current_setting('app.tenant_id'));
```

### API Security Best Practices

```python
# Rate limiting configuration
RATE_LIMITING_CONFIG = {
    "free": {"requests_per_hour": 100, "burst": 10},
    "basic": {"requests_per_hour": 1000, "burst": 50},
    "professional": {"requests_per_hour": 10000, "burst": 200},
    "enterprise": {"requests_per_hour": 100000, "burst": 1000}
}

# API key validation
def validate_api_key(api_key: str) -> bool:
    # Implement proper key validation
    if len(api_key) < 32:
        return False
    # Additional validation logic
    return True

# Input sanitization
def sanitize_input(data: dict) -> dict:
    # Remove potentially dangerous characters
    # Validate all input parameters
    return sanitized_data
```

## Scaling & Performance

### Horizontal Scaling

#### Application Scaling
```yaml
# Kubernetes HPA configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: async-scraper-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: async-scraper
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Database Scaling
```yaml
# PostgreSQL cluster with read replicas
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-cluster
spec:
  instances: 3
  primaryUpdateStrategy: unsupervised
  
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "256MB"
      effective_cache_size: "1GB"
      
  bootstrap:
    initdb:
      database: async_scraper
      owner: scraper_user
      
  monitoring:
    enabled: true
```

### Performance Optimization

#### Application Performance
```python
# Connection pooling configuration
DATABASE_CONFIG = {
    "pool_size": 20,
    "max_overflow": 30,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "echo": False
}

# Redis connection pooling
REDIS_CONFIG = {
    "connection_pool_kwargs": {
        "max_connections": 50,
        "retry_on_timeout": True,
        "socket_keepalive": True,
        "socket_keepalive_options": {}
    }
}

# Browser pool optimization
BROWSER_CONFIG = {
    "max_browsers": 10,
    "max_contexts_per_browser": 20,
    "browser_pool_timeout": 30,
    "context_pool_timeout": 10
}
```

#### Cache Optimization
```python
# Multi-layer cache configuration
CACHE_CONFIG = {
    "l1": {
        "enabled": True,
        "max_size": 10000,
        "ttl": 300  # 5 minutes
    },
    "l2": {
        "enabled": True,
        "redis_url": "redis://redis-cluster:6379",
        "ttl": 3600,  # 1 hour
        "key_prefix": "async_scraper:"
    },
    "l3": {
        "enabled": True,
        "directory": "/var/cache/async_scraper",
        "ttl": 86400,  # 24 hours
        "max_size_gb": 10
    }
}
```

## Backup & Recovery

### Database Backup Strategy

```bash
#!/bin/bash
# backup-database.sh

DATABASE_HOST="postgres-cluster"
DATABASE_NAME="async_scraper"
BACKUP_DIR="/backups"
RETENTION_DAYS=30

# Create timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/async_scraper_${TIMESTAMP}.sql"

# Create backup
pg_dump -h ${DATABASE_HOST} -d ${DATABASE_NAME} -f ${BACKUP_FILE}

# Compress backup
gzip ${BACKUP_FILE}

# Upload to cloud storage (AWS S3 example)
aws s3 cp ${BACKUP_FILE}.gz s3://your-backup-bucket/database/

# Clean old backups
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +${RETENTION_DAYS} -delete

# Verify backup integrity
if [ $? -eq 0 ]; then
    echo "✅ Backup completed successfully: ${BACKUP_FILE}.gz"
else
    echo "❌ Backup failed!"
    exit 1
fi
```

### Redis Backup
```bash
#!/bin/bash
# backup-redis.sh

REDIS_HOST="redis-cluster"
REDIS_PORT=6379
BACKUP_DIR="/backups/redis"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create Redis backup
redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} --rdb ${BACKUP_DIR}/dump_${TIMESTAMP}.rdb

# Compress and upload
gzip ${BACKUP_DIR}/dump_${TIMESTAMP}.rdb
aws s3 cp ${BACKUP_DIR}/dump_${TIMESTAMP}.rdb.gz s3://your-backup-bucket/redis/
```

### Disaster Recovery Plan

1. **Database Recovery**
   ```bash
   # Restore from backup
   gunzip async_scraper_backup.sql.gz
   psql -h postgres-cluster -d async_scraper < async_scraper_backup.sql
   ```

2. **Redis Recovery**
   ```bash
   # Stop Redis
   systemctl stop redis
   
   # Restore RDB file
   gunzip dump_backup.rdb.gz
   cp dump_backup.rdb /var/lib/redis/dump.rdb
   chown redis:redis /var/lib/redis/dump.rdb
   
   # Start Redis
   systemctl start redis
   ```

3. **Application Recovery**
   ```bash
   # Update deployment with backup image
   kubectl set image deployment/async-scraper \
     async-scraper=async-scraper:backup-tag
   
   # Verify health
   kubectl rollout status deployment/async-scraper
   ```

## Troubleshooting

### Common Issues

#### High Memory Usage
```bash
# Check memory usage by component
docker stats

# Analyze browser memory usage
curl -H "X-API-Key: admin-key" \
  "http://localhost:8000/admin/monitoring/stats" | jq '.browser_stats'

# Tune browser pool settings
export SCRAPER_BROWSER_MAX_BROWSERS=5
export SCRAPER_BROWSER_MAX_CONTEXTS_PER_BROWSER=10
```

#### Database Connection Issues
```bash
# Check database health
curl -H "X-API-Key: admin-key" \
  "http://localhost:8000/admin/monitoring/health" | jq '.checks.database'

# Check connection pool
psql -h postgres-cluster -c "SELECT * FROM pg_stat_activity;"

# Tune connection settings
export SCRAPER_DATABASE_CONNECTION_POOL_SIZE=10
export SCRAPER_DATABASE_MAX_OVERFLOW=20
```

#### Queue Performance Issues
```bash
# Check queue statistics
curl -H "X-API-Key: admin-key" \
  "http://localhost:8000/admin/monitoring/stats" | jq '.queue_stats'

# Monitor Redis performance
redis-cli -h redis-cluster INFO stats

# Scale queue workers
export SCRAPER_QUEUE_MAX_WORKERS=20
```

### Debugging Tools

#### Log Analysis
```bash
# Filter logs by tenant
docker logs async-scraper | jq 'select(.tenant_id == "tenant-123")'

# Monitor API errors
docker logs async-scraper | grep "ERROR" | tail -n 50

# Real-time log monitoring
docker logs -f async-scraper | jq 'select(.level == "ERROR")'
```

#### Performance Profiling
```python
# Enable performance profiling
import cProfile
import pstats

# Profile a specific endpoint
profiler = cProfile.Profile()
profiler.enable()

# Your application code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

#### Health Check Script
```bash
#!/bin/bash
# health-check.sh

API_BASE="http://localhost:8000"
ADMIN_KEY="admin-key"

echo "🔍 Checking Async Scraper Health..."

# Basic health check
HEALTH=$(curl -s ${API_BASE}/health)
if [[ $(echo $HEALTH | jq -r '.status') == "healthy" ]]; then
    echo "✅ Basic health check: PASSED"
else
    echo "❌ Basic health check: FAILED"
fi

# Detailed health check
DETAILED_HEALTH=$(curl -s -H "X-API-Key: ${ADMIN_KEY}" ${API_BASE}/admin/monitoring/health)
DATABASE_STATUS=$(echo $DETAILED_HEALTH | jq -r '.checks.database.status')
QUEUE_STATUS=$(echo $DETAILED_HEALTH | jq -r '.checks.queue.status')

echo "🗄️  Database: ${DATABASE_STATUS}"
echo "📋 Queue: ${QUEUE_STATUS}"

# Check system stats
STATS=$(curl -s -H "X-API-Key: ${ADMIN_KEY}" ${API_BASE}/admin/monitoring/stats)
ACTIVE_JOBS=$(echo $STATS | jq -r '.jobs.active')
ACTIVE_BROWSERS=$(echo $STATS | jq -r '.browser_stats.active_sessions')

echo "🏃 Active jobs: ${ACTIVE_JOBS}"
echo "🌐 Active browsers: ${ACTIVE_BROWSERS}"
```

This deployment guide provides comprehensive instructions for deploying Async_Scraper in various environments, from development to enterprise production with multi-tenancy support, monitoring, and operational best practices.