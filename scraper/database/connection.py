"""
Database connection management using asyncpg for PostgreSQL and aiosqlite for SQLite.
"""

import asyncio
import aiosqlite
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator, Dict, Any, Union
import structlog

from scraper.core.config import get_config
from scraper.core.logger import get_logger

logger = get_logger(__name__)

# Try to import asyncpg for PostgreSQL
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg not available, PostgreSQL support disabled")


class DatabaseManager:
    """Manages database connections and connection pooling."""
    
    def __init__(self):
        self.pool: Optional[Union[asyncpg.Pool, str]] = None  # Pool for PostgreSQL, path for SQLite
        self.config = get_config()
        self._lock = asyncio.Lock()
        self._sqlite_conn: Optional[aiosqlite.Connection] = None
    
    async def initialize(self) -> None:
        """Initialize database connection pool."""
        if self.pool or self._sqlite_conn:
            return
            
        async with self._lock:
            if self.pool or self._sqlite_conn:  # Double check after acquiring lock
                return
                
            try:
                db_config = self.config.database
                
                if db_config.use_sqlite:
                    # SQLite initialization
                    import os
                    os.makedirs(os.path.dirname(db_config.sqlite_path), exist_ok=True)
                    
                    self._sqlite_conn = await aiosqlite.connect(db_config.sqlite_path)
                    # Enable foreign keys for SQLite
                    await self._sqlite_conn.execute("PRAGMA foreign_keys = ON")
                    
                    logger.info(
                        "SQLite database initialized",
                        database_path=db_config.sqlite_path,
                    )
                    
                else:
                    # PostgreSQL initialization
                    if not ASYNCPG_AVAILABLE:
                        raise RuntimeError("asyncpg not available for PostgreSQL support")
                    
                    dsn = f"postgresql://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.database}"
                    
                    self.pool = await asyncpg.create_pool(
                        dsn,
                        min_size=db_config.min_connections,
                        max_size=db_config.max_connections,
                        command_timeout=db_config.command_timeout,
                    )
                    
                    logger.info(
                        "PostgreSQL database pool initialized",
                        host=db_config.host,
                        database=db_config.database,
                        min_connections=db_config.min_connections,
                        max_connections=db_config.max_connections,
                    )
                
                # Run initial health check
                await self.health_check()
                
            except Exception as e:
                logger.error("Failed to initialize database", error=str(e))
                raise
    
    async def close(self) -> None:
        """Close database connection pool."""
        if self.config.database.use_sqlite:
            if self._sqlite_conn:
                await self._sqlite_conn.close()
                self._sqlite_conn = None
                logger.info("SQLite database connection closed")
        else:
            if self.pool:
                await self.pool.close()
                self.pool = None
                logger.info("PostgreSQL database pool closed")
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            result = await self.fetchval("SELECT 1")
            return result == 1
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Union[asyncpg.Connection, aiosqlite.Connection], None]:
        """Get database connection from pool."""
        if not self.pool and not self._sqlite_conn:
            await self.initialize()
        
        if self.config.database.use_sqlite:
            yield self._sqlite_conn
        else:
            async with self.pool.acquire() as conn:
                yield conn
    
    async def execute(self, query: str, *args: Any) -> str:
        """Execute a command and return status."""
        async with self.get_connection() as conn:
            if self.config.database.use_sqlite:
                await conn.execute(query, args)
                await conn.commit()
                return "OK"  # SQLite doesn't return status like PostgreSQL
            else:
                return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args: Any) -> list[dict]:
        """Fetch multiple rows as dictionaries."""
        async with self.get_connection() as conn:
            if self.config.database.use_sqlite:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(query, args)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
            else:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
    
    async def fetchrow(self, query: str, *args: Any) -> Optional[dict]:
        """Fetch single row as dictionary."""
        async with self.get_connection() as conn:
            if self.config.database.use_sqlite:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(query, args)
                row = await cursor.fetchone()
                return dict(row) if row else None
            else:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
    
    async def fetchval(self, query: str, *args: Any) -> Any:
        """Fetch single value."""
        async with self.get_connection() as conn:
            if self.config.database.use_sqlite:
                cursor = await conn.execute(query, args)
                row = await cursor.fetchone()
                return row[0] if row else None
            else:
                return await conn.fetchval(query, *args)
    
    async def transaction(self):
        """Start a database transaction."""
        if not self.pool and not self._sqlite_conn:
            await self.initialize()
        
        if self.config.database.use_sqlite:
            return self._sqlite_conn  # SQLite handles transactions automatically
        else:
            return self.pool.acquire()


# Global database manager instance
_database_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager