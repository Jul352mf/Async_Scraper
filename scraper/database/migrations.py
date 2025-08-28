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
        
        # Determine if we're using SQLite
        is_sqlite = db.config.database.use_sqlite
        
        # Create migrations tracking table first
        await db.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                version INTEGER NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create jobs table
        if is_sqlite:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    config TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    progress TEXT DEFAULT '{}',
                    error_message TEXT,
                    result_count INTEGER
                )
            """)
        else:
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
                    result_count INTEGER
                )
            """)
        
        # Create indexes for jobs table
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_updated_at ON jobs(updated_at)")
        
        # Create job_results table
        if is_sqlite:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS job_results (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    result_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
                )
            """)
        else:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS job_results (
                    id VARCHAR(36) PRIMARY KEY,
                    job_id VARCHAR(36) NOT NULL,
                    result_type VARCHAR(20) NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
        
        # Add foreign key constraint (PostgreSQL only - SQLite has it in table definition)
        if not is_sqlite:
            await db.execute("""
                ALTER TABLE job_results 
                ADD CONSTRAINT IF NOT EXISTS fk_job_results_job_id 
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            """)
        
        # Create indexes for job_results table
        await db.execute("CREATE INDEX IF NOT EXISTS idx_job_results_job_id ON job_results(job_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_job_results_type ON job_results(result_type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_job_results_created_at ON job_results(created_at)")
        
        # Create proxies table
        if is_sqlite:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS proxies (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    description TEXT,
                    username TEXT,
                    password TEXT,
                    country TEXT,
                    tags TEXT DEFAULT '[]',
                    is_active INTEGER DEFAULT 1,
                    health_status TEXT DEFAULT 'unknown',
                    success_rate REAL DEFAULT 0.0,
                    avg_response_time REAL,
                    last_used TIMESTAMP,
                    last_health_check TIMESTAMP,
                    consecutive_failures INTEGER DEFAULT 0,
                    is_blacklisted INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
        else:
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
                    updated_at TIMESTAMP WITH TIME ZONE
                )
            """)
        
        # Create indexes for proxies table
        await db.execute("CREATE INDEX IF NOT EXISTS idx_proxies_active ON proxies(is_active)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_proxies_health_status ON proxies(health_status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_proxies_country ON proxies(country)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_proxies_success_rate ON proxies(success_rate)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_proxies_is_blacklisted ON proxies(is_blacklisted)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_proxies_last_health_check ON proxies(last_health_check)")
        
        logger.info("Initial database schema created successfully")
    
    async def down(self, db: DatabaseManager) -> None:
        """Drop initial database schema."""
        logger.info("Dropping initial database schema")
        
        await db.execute("DROP TABLE IF EXISTS job_results CASCADE")
        await db.execute("DROP TABLE IF EXISTS jobs CASCADE")
        await db.execute("DROP TABLE IF EXISTS proxies CASCADE")
        await db.execute("DROP TABLE IF EXISTS migrations CASCADE")
        
        logger.info("Initial database schema dropped")


class TenantMigration(Migration):
    """Add multi-tenancy support migration."""
    
    def __init__(self):
        super().__init__("add_tenant_support", 2)
    
    async def up(self, db: DatabaseManager) -> None:
        """Add tenant-related tables and columns."""
        logger.info("Adding tenant support to database schema")
        
        # Determine if we're using SQLite
        is_sqlite = db.config.database.use_sqlite
        
        # Create tenants table
        if is_sqlite:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    quotas TEXT NOT NULL,
                    usage TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
        else:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id VARCHAR(36) PRIMARY KEY,
                    config JSONB NOT NULL,
                    quotas JSONB NOT NULL,
                    usage JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE
                )
            """)
        
        # Create indexes for tenants table
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tenants_created_at ON tenants(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tenants_updated_at ON tenants(updated_at)")
        
        # Add tenant_id column to existing tables
        try:
            # Add tenant_id to jobs table
            if is_sqlite:
                await db.execute("ALTER TABLE jobs ADD COLUMN tenant_id TEXT")
            else:
                await db.execute("ALTER TABLE jobs ADD COLUMN tenant_id VARCHAR(36)")
                
            # Add tenant_id to job_results table
            if is_sqlite:
                await db.execute("ALTER TABLE job_results ADD COLUMN tenant_id TEXT")
            else:
                await db.execute("ALTER TABLE job_results ADD COLUMN tenant_id VARCHAR(36)")
                
            # Add tenant_id to proxies table
            if is_sqlite:
                await db.execute("ALTER TABLE proxies ADD COLUMN tenant_id TEXT")
            else:
                await db.execute("ALTER TABLE proxies ADD COLUMN tenant_id VARCHAR(36)")
                
        except Exception as e:
            # Columns might already exist
            logger.warning("Failed to add tenant_id columns", error=str(e))
        
        # Create indexes for tenant_id columns
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_tenant_id ON jobs(tenant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_job_results_tenant_id ON job_results(tenant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_proxies_tenant_id ON proxies(tenant_id)")
        
        # Create API keys table for tenant authentication
        if is_sqlite:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    name TEXT,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                )
            """)
        else:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id VARCHAR(36) PRIMARY KEY,
                    tenant_id VARCHAR(36) NOT NULL,
                    key_hash VARCHAR(255) NOT NULL UNIQUE,
                    name VARCHAR(255),
                    description TEXT,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_used TIMESTAMP WITH TIME ZONE,
                    expires_at TIMESTAMP WITH TIME ZONE
                )
            """)
        
        # Add foreign key constraint for API keys (PostgreSQL only)
        if not is_sqlite:
            await db.execute("""
                ALTER TABLE api_keys 
                ADD CONSTRAINT IF NOT EXISTS fk_api_keys_tenant_id 
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
            """)
        
        # Create indexes for api_keys table
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_tenant_id ON api_keys(tenant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at)")
        
        # Create job_logs table for detailed logging
        if is_sqlite:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS job_logs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    tenant_id TEXT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
                )
            """)
        else:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS job_logs (
                    id VARCHAR(36) PRIMARY KEY,
                    job_id VARCHAR(36) NOT NULL,
                    tenant_id VARCHAR(36),
                    level VARCHAR(20) NOT NULL,
                    message TEXT NOT NULL,
                    details JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
        
        # Add foreign key constraint for job logs (PostgreSQL only)
        if not is_sqlite:
            await db.execute("""
                ALTER TABLE job_logs 
                ADD CONSTRAINT IF NOT EXISTS fk_job_logs_job_id 
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            """)
        
        # Create indexes for job_logs table
        await db.execute("CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs(job_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_job_logs_tenant_id ON job_logs(tenant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_job_logs_level ON job_logs(level)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_job_logs_created_at ON job_logs(created_at)")
        
        logger.info("Tenant support added to database schema successfully")
    
    async def down(self, db: DatabaseManager) -> None:
        """Remove tenant-related tables and columns."""
        logger.info("Removing tenant support from database schema")
        
        # Drop tenant-related tables
        await db.execute("DROP TABLE IF EXISTS job_logs CASCADE")
        await db.execute("DROP TABLE IF EXISTS api_keys CASCADE")
        await db.execute("DROP TABLE IF EXISTS tenants CASCADE")
        
        # Remove tenant_id columns (this is tricky in SQLite, so we'll skip it)
        # In production, you'd want to recreate tables without these columns
        
        logger.info("Tenant support removed from database schema")


# List of all migrations in order
MIGRATIONS: List[Migration] = [
    InitialMigration(),
    TenantMigration(),
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
                if db.config.database.use_sqlite:
                    # SQLite transactions
                    await conn.execute("BEGIN")
                    try:
                        await migration.up(db)
                        
                        # Record migration
                        await conn.execute(
                            "INSERT INTO migrations (name, version) VALUES (?, ?)",
                            (migration.name, migration.version)
                        )
                        await conn.execute("COMMIT")
                    except Exception:
                        await conn.execute("ROLLBACK")
                        raise
                else:
                    # PostgreSQL transactions
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
                if db.config.database.use_sqlite:
                    # SQLite transactions
                    await conn.execute("BEGIN")
                    try:
                        await migration.down(db)
                        
                        # Remove migration record
                        await conn.execute(
                            "DELETE FROM migrations WHERE name = ? AND version = ?",
                            (migration.name, migration.version)
                        )
                        await conn.execute("COMMIT")
                    except Exception:
                        await conn.execute("ROLLBACK")
                        raise
                else:
                    # PostgreSQL transactions
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