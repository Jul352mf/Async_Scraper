"""
Database connection management using asyncpg for PostgreSQL.
"""

import asyncio
import asyncpg
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator, Dict, Any
import structlog

from scraper.core.config import get_config
from scraper.core.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database connections and connection pooling."""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.config = get_config()
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize database connection pool."""
        if self.pool:
            return
            
        async with self._lock:
            if self.pool:  # Double check after acquiring lock
                return
                
            try:
                # Build connection string from config
                db_config = self.config.database
                dsn = f"postgresql://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.database}"
                
                self.pool = await asyncpg.create_pool(
                    dsn,
                    min_size=db_config.min_connections,
                    max_size=db_config.max_connections,
                    command_timeout=db_config.command_timeout,
                )
                
                logger.info(
                    "Database pool initialized",
                    host=db_config.host,
                    database=db_config.database,
                    min_connections=db_config.min_connections,
                    max_connections=db_config.max_connections,
                )
                
                # Run initial health check
                await self.health_check()
                
            except Exception as e:
                logger.error("Failed to initialize database pool", error=str(e))
                raise
    
    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        if not self.pool:
            return False
            
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get database connection from pool."""
        if not self.pool:
            await self.initialize()
            
        async with self.pool.acquire() as conn:
            yield conn
    
    async def execute(self, query: str, *args: Any) -> str:
        """Execute a command and return status."""
        async with self.get_connection() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args: Any) -> list[dict]:
        """Fetch multiple rows as dictionaries."""
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def fetchrow(self, query: str, *args: Any) -> Optional[dict]:
        """Fetch single row as dictionary."""
        async with self.get_connection() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def fetchval(self, query: str, *args: Any) -> Any:
        """Fetch single value."""
        async with self.get_connection() as conn:
            return await conn.fetchval(query, *args)
    
    async def transaction(self):
        """Start a database transaction."""
        if not self.pool:
            await self.initialize()
            
        return self.pool.acquire()


# Global database manager instance
_database_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager