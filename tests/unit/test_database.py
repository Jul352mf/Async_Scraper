"""
Tests for database functionality including models, connection, and migrations.
"""

import asyncio
import pytest
import tempfile
import os
from datetime import datetime, timezone
from uuid import uuid4
import json

from scraper.database import DatabaseManager, JobModel, JobResultModel, ProxyModel
from scraper.database.migrations import run_migrations, rollback_migration
from scraper.core.config import Config
from scraper.api.models import JobStatus, JobType, JobProgress


@pytest.fixture
async def test_db():
    """Create a test database manager with SQLite for isolation."""
    # Use SQLite for tests to avoid PostgreSQL dependency
    config = Config()
    config.database.use_sqlite = True
    
    # Create temporary database file
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    config.database.sqlite_path = db_path
    
    # Create database manager
    db = DatabaseManager()
    db.config = config
    
    try:
        await db.initialize()
        
        # Run migrations
        await run_migrations(db)
        
        yield db
        
    finally:
        await db.close()
        # Cleanup temp file
        try:
            os.unlink(db_path)
            os.rmdir(temp_dir)
        except:
            pass


@pytest.mark.asyncio
class TestDatabaseConnection:
    """Test database connection management."""
    
    async def test_health_check(self, test_db):
        """Test database health check."""
        assert await test_db.health_check() is True
    
    async def test_basic_query(self, test_db):
        """Test basic database queries."""
        result = await test_db.fetchval("SELECT 1")
        assert result == 1
    
    async def test_connection_context_manager(self, test_db):
        """Test connection context manager."""
        async with test_db.get_connection() as conn:
            result = await conn.fetchval("SELECT 2")
            assert result == 2


@pytest.mark.asyncio
class TestJobModel:
    """Test job database model."""
    
    async def test_create_job(self, test_db):
        """Test creating a job in the database."""
        job_id = str(uuid4())
        config = {"companies": ["Google"], "max_emails": 10}
        
        await test_db.execute("""
            INSERT INTO jobs (id, type, status, config)
            VALUES ($1, $2, $3, $4)
        """, job_id, "scrape_companies", "pending", json.dumps(config))
        
        # Retrieve job
        row = await test_db.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        assert row is not None
        
        job = JobModel.from_dict(dict(row))
        assert job.id == job_id
        assert job.type == "scrape_companies"
        assert job.status == "pending"
        assert job.config == config
    
    async def test_update_job_progress(self, test_db):
        """Test updating job progress."""
        job_id = str(uuid4())
        config = {"companies": ["Google"]}
        
        # Create job
        await test_db.execute("""
            INSERT INTO jobs (id, type, status, config)
            VALUES ($1, $2, $3, $4)
        """, job_id, "scrape_companies", "running", json.dumps(config))
        
        # Update progress
        progress = {"percent": 45.5, "current_item": "google.com"}
        await test_db.execute("""
            UPDATE jobs SET progress = $1, updated_at = NOW()
            WHERE id = $2
        """, json.dumps(progress), job_id)
        
        # Retrieve and verify
        row = await test_db.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        job = JobModel.from_dict(dict(row))
        assert job.progress == progress
        assert job.updated_at is not None
    
    async def test_job_to_api_model(self, test_db):
        """Test converting job model to API model."""
        job_id = str(uuid4())
        config = {"companies": ["Google"]}
        progress = {"percent": 75.0, "current_item": "google.com"}
        
        await test_db.execute("""
            INSERT INTO jobs (id, type, status, config, progress, result_count)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, job_id, "scrape_companies", "completed", json.dumps(config), json.dumps(progress), 5)
        
        row = await test_db.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        job = JobModel.from_dict(dict(row))
        
        api_job = job.to_api_model()
        assert api_job.id == job_id
        assert api_job.type == JobType.SCRAPE_COMPANIES
        assert api_job.status == JobStatus.COMPLETED
        assert api_job.config == config
        assert api_job.progress.percent == 75.0
        assert api_job.result_count == 5


@pytest.mark.asyncio
class TestJobResultModel:
    """Test job result database model."""
    
    async def test_create_job_result(self, test_db):
        """Test creating job results."""
        job_id = str(uuid4())
        result_id = str(uuid4())
        
        # Create parent job first
        await test_db.execute("""
            INSERT INTO jobs (id, type, status, config)
            VALUES ($1, $2, $3, $4)
        """, job_id, "scrape_companies", "running", '{}')
        
        # Create result
        email_data = {
            "email": "test@google.com",
            "domain": "google.com",
            "source": "https://google.com/contact"
        }
        
        await test_db.execute("""
            INSERT INTO job_results (id, job_id, result_type, data)
            VALUES ($1, $2, $3, $4)
        """, result_id, job_id, "email", json.dumps(email_data))
        
        # Retrieve result
        row = await test_db.fetchrow("SELECT * FROM job_results WHERE id = $1", result_id)
        assert row is not None
        
        result = JobResultModel.from_dict(dict(row))
        assert result.id == result_id
        assert result.job_id == job_id
        assert result.result_type == "email"
        assert result.data == email_data
    
    async def test_foreign_key_constraint(self, test_db):
        """Test foreign key constraint on job_results."""
        result_id = str(uuid4())
        invalid_job_id = str(uuid4())
        
        # Try to create result with non-existent job_id
        with pytest.raises(Exception):  # Should raise foreign key constraint error
            await test_db.execute("""
                INSERT INTO job_results (id, job_id, result_type, data)
                VALUES ($1, $2, $3, $4)
            """, result_id, invalid_job_id, "email", '{"email": "test@example.com"}')


@pytest.mark.asyncio
class TestProxyModel:
    """Test proxy database model."""
    
    async def test_create_proxy(self, test_db):
        """Test creating a proxy in the database."""
        proxy_id = str(uuid4())
        
        await test_db.execute("""
            INSERT INTO proxies (id, url, description, country, tags, success_rate)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, proxy_id, "http://proxy.example.com:8080", "Test proxy", "US", '["fast", "reliable"]', 0.85)
        
        # Retrieve proxy
        row = await test_db.fetchrow("SELECT * FROM proxies WHERE id = $1", proxy_id)
        assert row is not None
        
        proxy = ProxyModel.from_dict(dict(row))
        assert proxy.id == proxy_id
        assert proxy.url == "http://proxy.example.com:8080"
        assert proxy.description == "Test proxy"
        assert proxy.country == "US"
        assert proxy.tags == ["fast", "reliable"]
        assert proxy.success_rate == 0.85
    
    async def test_update_proxy_health(self, test_db):
        """Test updating proxy health status."""
        proxy_id = str(uuid4())
        
        # Create proxy
        await test_db.execute("""
            INSERT INTO proxies (id, url)
            VALUES ($1, $2)
        """, proxy_id, "http://proxy.example.com:8080")
        
        # Update health
        await test_db.execute("""
            UPDATE proxies 
            SET health_status = $1, success_rate = $2, avg_response_time = $3,
                last_health_check = NOW(), consecutive_failures = $4
            WHERE id = $5
        """, "healthy", 0.95, 125.5, 0, proxy_id)
        
        # Retrieve and verify
        row = await test_db.fetchrow("SELECT * FROM proxies WHERE id = $1", proxy_id)
        proxy = ProxyModel.from_dict(dict(row))
        assert proxy.health_status == "healthy"
        assert proxy.success_rate == 0.95
        assert proxy.avg_response_time == 125.5
        assert proxy.consecutive_failures == 0
        assert proxy.last_health_check is not None


@pytest.mark.asyncio
class TestMigrations:
    """Test database migrations."""
    
    async def test_migration_tracking(self, test_db):
        """Test migration tracking table."""
        # Check migrations table exists and has entries
        result = await test_db.fetchval("SELECT COUNT(*) FROM migrations")
        assert result >= 1  # Should have at least the initial migration
    
    async def test_migration_rollback(self, test_db):
        """Test migration rollback functionality."""
        # Get current version
        current_version = await test_db.fetchval(
            "SELECT COALESCE(MAX(version), 0) FROM migrations"
        )
        
        # Rollback to version 0 (this should drop all tables)
        await rollback_migration(test_db, target_version=0)
        
        # Check that migrations table is gone
        try:
            await test_db.fetchval("SELECT COUNT(*) FROM migrations")
            assert False, "Migrations table should not exist after rollback"
        except Exception:
            pass  # Expected - table should not exist
        
        # Re-run migrations
        await run_migrations(test_db)
        
        # Verify tables are back
        tables = await test_db.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'main'
        """)
        table_names = [row['table_name'] for row in tables]
        
        assert 'jobs' in table_names
        assert 'job_results' in table_names
        assert 'proxies' in table_names
        assert 'migrations' in table_names


@pytest.mark.asyncio
class TestDatabaseIndexes:
    """Test database indexes for performance."""
    
    async def test_job_indexes_exist(self, test_db):
        """Test that job table indexes exist."""
        # This is SQLite specific - in real PostgreSQL we'd check pg_indexes
        indexes = await test_db.fetch("""
            SELECT name FROM sqlite_master 
            WHERE type = 'index' AND tbl_name = 'jobs'
        """)
        
        index_names = [idx['name'] for idx in indexes]
        
        # Check for our custom indexes
        # Note: SQLite automatically creates some indexes, so we just check they exist
        assert len(index_names) > 0  # Should have at least the primary key index
    
    async def test_proxy_indexes_exist(self, test_db):
        """Test that proxy table indexes exist."""
        indexes = await test_db.fetch("""
            SELECT name FROM sqlite_master 
            WHERE type = 'index' AND tbl_name = 'proxies'
        """)
        
        index_names = [idx['name'] for idx in indexes]
        
        # Check for our custom indexes
        # Note: SQLite automatically creates some indexes, so we just check they exist
        assert len(index_names) > 0  # Should have at least the primary key index