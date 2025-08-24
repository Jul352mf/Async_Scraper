"""
Database migrations and schema management.
"""

import asyncio
from typing import List
import structlog

from scraper.database.connection import DatabaseManager
from scraper.core.logger import get_logger

logger = get_logger(__name__)


class Migration:
    """Base migration class."""
    
    def __init__(self, name: str, version: int):
        self.name = name
        self.version = version
    
    async def up(self, db: DatabaseManager) -> None:
        """Apply migration."""
        raise NotImplementedError
    
    async def down(self, db: DatabaseManager) -> None:
        """Rollback migration."""
        raise NotImplementedError


class InitialMigration(Migration):
    """Initial database schema migration."""
    
    def __init__(self):
        super().__init__("initial_schema", 1)
    
    async def up(self, db: DatabaseManager) -> None:
        """Create initial database schema."""
        logger.info("Creating initial database schema")
        
        # Create migrations tracking table first
        await db.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                version INTEGER NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Create jobs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id VARCHAR(36) PRIMARY KEY,
                type VARCHAR(50) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                config JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE,
                started_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                progress JSONB DEFAULT '{}',
                error_message TEXT,
                result_count INTEGER,
                
                -- Indexes for common queries
                INDEX idx_jobs_status (status),
                INDEX idx_jobs_type (type),
                INDEX idx_jobs_created_at (created_at),
                INDEX idx_jobs_updated_at (updated_at)
            )
        """)
        
        # Create job_results table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS job_results (
                id VARCHAR(36) PRIMARY KEY,
                job_id VARCHAR(36) NOT NULL,
                result_type VARCHAR(20) NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                
                -- Foreign key
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                
                -- Indexes
                INDEX idx_job_results_job_id (job_id),
                INDEX idx_job_results_type (result_type),
                INDEX idx_job_results_created_at (created_at)
            )
        """)
        
        # Create proxies table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS proxies (
                id VARCHAR(36) PRIMARY KEY,
                url VARCHAR(500) NOT NULL UNIQUE,
                description TEXT,
                username VARCHAR(255),
                password VARCHAR(255),
                country VARCHAR(2),
                tags JSONB DEFAULT '[]',
                is_active BOOLEAN DEFAULT true,
                health_status VARCHAR(20) DEFAULT 'unknown',
                success_rate FLOAT DEFAULT 0.0,
                avg_response_time FLOAT,
                last_used TIMESTAMP WITH TIME ZONE,
                last_health_check TIMESTAMP WITH TIME ZONE,
                consecutive_failures INTEGER DEFAULT 0,
                is_blacklisted BOOLEAN DEFAULT false,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE,
                
                -- Indexes
                INDEX idx_proxies_active (is_active),
                INDEX idx_proxies_health_status (health_status),
                INDEX idx_proxies_country (country),
                INDEX idx_proxies_success_rate (success_rate),
                INDEX idx_proxies_is_blacklisted (is_blacklisted),
                INDEX idx_proxies_last_health_check (last_health_check)
            )
        """)
        
        logger.info("Initial database schema created successfully")
    
    async def down(self, db: DatabaseManager) -> None:
        """Drop initial database schema."""
        logger.info("Dropping initial database schema")
        
        await db.execute("DROP TABLE IF EXISTS job_results CASCADE")
        await db.execute("DROP TABLE IF EXISTS jobs CASCADE")
        await db.execute("DROP TABLE IF EXISTS proxies CASCADE")
        await db.execute("DROP TABLE IF EXISTS migrations CASCADE")
        
        logger.info("Initial database schema dropped")


# List of all migrations in order
MIGRATIONS: List[Migration] = [
    InitialMigration(),
]


async def run_migrations(db: DatabaseManager) -> None:
    """Run all pending migrations."""
    logger.info("Starting database migrations")
    
    try:
        # Ensure database is connected
        await db.initialize()
        
        # Get current migration version
        try:
            current_version = await db.fetchval(
                "SELECT COALESCE(MAX(version), 0) FROM migrations"
            )
        except Exception:
            # Migrations table might not exist yet
            current_version = 0
        
        logger.info("Current migration version", version=current_version)
        
        # Apply pending migrations
        pending_migrations = [m for m in MIGRATIONS if m.version > current_version]
        
        if not pending_migrations:
            logger.info("No pending migrations")
            return
        
        logger.info("Applying migrations", count=len(pending_migrations))
        
        for migration in pending_migrations:
            logger.info("Applying migration", name=migration.name, version=migration.version)
            
            # Use transaction for each migration
            async with db.get_connection() as conn:
                async with conn.transaction():
                    await migration.up(db)
                    
                    # Record migration
                    await conn.execute(
                        "INSERT INTO migrations (name, version) VALUES ($1, $2)",
                        migration.name,
                        migration.version,
                    )
            
            logger.info("Migration applied successfully", name=migration.name, version=migration.version)
        
        logger.info("All migrations completed successfully")
        
    except Exception as e:
        logger.error("Migration failed", error=str(e))
        raise


async def rollback_migration(db: DatabaseManager, target_version: int = 0) -> None:
    """Rollback migrations to target version."""
    logger.info("Starting migration rollback", target_version=target_version)
    
    try:
        await db.initialize()
        
        # Get current version
        current_version = await db.fetchval(
            "SELECT COALESCE(MAX(version), 0) FROM migrations"
        )
        
        if current_version <= target_version:
            logger.info("Already at or below target version")
            return
        
        # Get migrations to rollback (in reverse order)
        rollback_migrations = [
            m for m in reversed(MIGRATIONS) 
            if target_version < m.version <= current_version
        ]
        
        logger.info("Rolling back migrations", count=len(rollback_migrations))
        
        for migration in rollback_migrations:
            logger.info("Rolling back migration", name=migration.name, version=migration.version)
            
            async with db.get_connection() as conn:
                async with conn.transaction():
                    await migration.down(db)
                    
                    # Remove migration record
                    await conn.execute(
                        "DELETE FROM migrations WHERE name = $1 AND version = $2",
                        migration.name,
                        migration.version,
                    )
            
            logger.info("Migration rolled back successfully", name=migration.name, version=migration.version)
        
        logger.info("Migration rollback completed")
        
    except Exception as e:
        logger.error("Migration rollback failed", error=str(e))
        raise