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