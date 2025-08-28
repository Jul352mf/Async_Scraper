"""Tenant data isolation utilities."""

from typing import Dict, Any, Optional, List
from sqlalchemy import text

from .models import TenantModel
from ..logger import get_logger

logger = get_logger(__name__)


class TenantIsolationManager:
    """Manages data isolation for multi-tenant operations."""
    
    def __init__(self):
        pass
        
    def add_tenant_filter(
        self, 
        query: str, 
        tenant_id: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> tuple[str, Dict[str, Any]]:
        """Add tenant filter to SQL query."""
        if params is None:
            params = {}
            
        # Add tenant filter to WHERE clause
        if "WHERE" in query.upper():
            filtered_query = query.replace(
                "WHERE", 
                f"WHERE tenant_id = :tenant_id AND", 
                1
            )
        else:
            # Add WHERE clause
            filtered_query = f"{query} WHERE tenant_id = :tenant_id"
            
        params["tenant_id"] = tenant_id
        
        return filtered_query, params
        
    def create_tenant_aware_insert(
        self,
        table: str,
        data: Dict[str, Any],
        tenant_id: str
    ) -> tuple[str, Dict[str, Any]]:
        """Create INSERT statement with tenant isolation."""
        # Add tenant_id to data
        data = data.copy()
        data["tenant_id"] = tenant_id
        
        # Build INSERT query
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f":{key}" for key in data.keys()])
        
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        return query, data
        
    def create_tenant_aware_update(
        self,
        table: str,
        data: Dict[str, Any],
        tenant_id: str,
        where_clause: str = "",
        where_params: Optional[Dict[str, Any]] = None
    ) -> tuple[str, Dict[str, Any]]:
        """Create UPDATE statement with tenant isolation."""
        if where_params is None:
            where_params = {}
            
        # Build SET clause
        set_clauses = [f"{key} = :{key}" for key in data.keys()]
        set_clause = ", ".join(set_clauses)
        
        # Combine parameters
        all_params = {**data, **where_params}
        all_params["tenant_id"] = tenant_id
        
        # Build query with tenant filter
        if where_clause:
            query = f"""
                UPDATE {table} 
                SET {set_clause}
                WHERE tenant_id = :tenant_id AND ({where_clause})
            """
        else:
            query = f"""
                UPDATE {table} 
                SET {set_clause}
                WHERE tenant_id = :tenant_id
            """
            
        return query.strip(), all_params
        
    def create_tenant_aware_delete(
        self,
        table: str,
        tenant_id: str,
        where_clause: str = "",
        where_params: Optional[Dict[str, Any]] = None
    ) -> tuple[str, Dict[str, Any]]:
        """Create DELETE statement with tenant isolation."""
        if where_params is None:
            where_params = {}
            
        params = where_params.copy()
        params["tenant_id"] = tenant_id
        
        # Build query with tenant filter
        if where_clause:
            query = f"""
                DELETE FROM {table}
                WHERE tenant_id = :tenant_id AND ({where_clause})
            """
        else:
            query = f"""
                DELETE FROM {table}
                WHERE tenant_id = :tenant_id
            """
            
        return query.strip(), params
        
    async def isolate_job_data(
        self,
        db,
        tenant: TenantModel,
        job_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ensure job data is properly isolated to tenant."""
        isolated_data = job_data.copy()
        isolated_data["tenant_id"] = tenant.tenant_id
        
        # Add tenant-specific metadata
        isolated_data["tenant_plan"] = tenant.config.plan.value
        isolated_data["tenant_features"] = {
            "javascript": tenant.has_feature("javascript"),
            "proxy": tenant.has_feature("proxy"),
            "webhook": tenant.has_feature("webhook"),
        }
        
        return isolated_data
        
    async def get_tenant_jobs(
        self,
        db,
        tenant_id: str,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get jobs for a specific tenant."""
        base_query = "SELECT * FROM jobs"
        params = {}
        
        # Add tenant filter
        query, params = self.add_tenant_filter(base_query, tenant_id, params)
        
        # Add status filter
        if status:
            query += " AND status = :status"
            params["status"] = status
            
        # Add ordering
        query += " ORDER BY created_at DESC"
        
        # Add pagination
        if limit:
            query += " LIMIT :limit OFFSET :offset"
            params["limit"] = limit
            params["offset"] = offset
        elif offset:
            query += " OFFSET :offset"
            params["offset"] = offset
            
        # Execute query
        rows = await db.fetchall(query, params)
        return [dict(row) for row in rows]
        
    async def cleanup_tenant_data(
        self,
        db,
        tenant_id: str,
        retention_days: int = 30
    ) -> Dict[str, int]:
        """Cleanup old data for a tenant."""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_date.isoformat()
        
        cleanup_stats = {}
        
        # Cleanup old completed jobs
        query, params = self.create_tenant_aware_delete(
            "jobs",
            tenant_id,
            "status IN ('completed', 'failed') AND created_at < :cutoff",
            {"cutoff": cutoff_timestamp}
        )
        
        result = await db.execute(query, params)
        cleanup_stats["jobs_deleted"] = getattr(result, 'rowcount', 0)
        
        # Cleanup old job results
        query, params = self.create_tenant_aware_delete(
            "job_results",
            tenant_id,
            "created_at < :cutoff",
            {"cutoff": cutoff_timestamp}
        )
        
        result = await db.execute(query, params)
        cleanup_stats["results_deleted"] = getattr(result, 'rowcount', 0)
        
        # Cleanup old logs
        query, params = self.create_tenant_aware_delete(
            "job_logs",
            tenant_id,
            "created_at < :cutoff",
            {"cutoff": cutoff_timestamp}
        )
        
        result = await db.execute(query, params)
        cleanup_stats["logs_deleted"] = getattr(result, 'rowcount', 0)
        
        logger.info(
            f"Cleaned up tenant data",
            tenant_id=tenant_id,
            **cleanup_stats
        )
        
        return cleanup_stats
        
    async def get_tenant_storage_usage(
        self,
        db,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Calculate storage usage for a tenant."""
        # Query job results storage
        query = """
            SELECT 
                COUNT(*) as result_count,
                COALESCE(SUM(LENGTH(COALESCE(results, ''))), 0) as results_size,
                COALESCE(SUM(LENGTH(COALESCE(error_details, ''))), 0) as error_size
            FROM job_results 
            WHERE tenant_id = :tenant_id
        """
        
        row = await db.fetchone(query, {"tenant_id": tenant_id})
        
        if row:
            results_mb = (row["results_size"] + row["error_size"]) / (1024 * 1024)
            
            return {
                "result_count": row["result_count"],
                "storage_used_mb": round(results_mb, 2),
                "results_size_bytes": row["results_size"],
                "error_size_bytes": row["error_size"]
            }
        else:
            return {
                "result_count": 0,
                "storage_used_mb": 0.0,
                "results_size_bytes": 0,
                "error_size_bytes": 0
            }
            
    def validate_tenant_access(
        self,
        tenant: TenantModel,
        resource_type: str,
        operation: str
    ) -> bool:
        """Validate if tenant can access a resource type and operation."""
        if not tenant.is_active():
            return False
            
        # Feature-based access control
        feature_requirements = {
            "javascript_scraping": "javascript",
            "proxy_usage": "proxy", 
            "webhook_delivery": "webhook",
            "advanced_config": "custom_headers",
        }
        
        required_feature = feature_requirements.get(resource_type)
        if required_feature and not tenant.has_feature(required_feature):
            return False
            
        # Operation-specific checks
        if operation == "create_job":
            return tenant.can_create_job()
        elif operation == "api_request":
            return tenant.can_make_request()
            
        return True