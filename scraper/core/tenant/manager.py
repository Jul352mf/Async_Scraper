"""Tenant management system."""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from .models import TenantModel, TenantConfig, TenantStatus, TenantPlan, TenantQuotas, TenantUsage
from ..logger import get_logger

logger = get_logger(__name__)


class TenantManager:
    """Manages tenant lifecycle and operations."""
    
    def __init__(self):
        self._tenants: Dict[str, TenantModel] = {}
        self._api_key_to_tenant: Dict[str, str] = {}  # API key -> tenant_id mapping
        self._cleanup_task: Optional[asyncio.Task] = None
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize tenant manager."""
        if self._initialized:
            return
            
        try:
            # Load tenants from database
            await self._load_tenants()
            
            # Start background tasks
            await self._start_background_tasks()
            
            self._initialized = True
            logger.info("Tenant manager initialized")
            
        except Exception as e:
            logger.error("Failed to initialize tenant manager", error=str(e))
            raise
            
    async def _load_tenants(self) -> None:
        """Load tenants from database."""
        try:
            from ...database import get_database_manager
            
            db = get_database_manager()
            
            # Query tenants from database
            rows = await db.fetchall(
                "SELECT * FROM tenants WHERE status != 'deleted'"
            )
            
            for row in rows:
                tenant = TenantModel.from_dict(dict(row))
                self._tenants[tenant.tenant_id] = tenant
                
            logger.info(f"Loaded {len(self._tenants)} tenants")
            
        except Exception as e:
            logger.warning("Failed to load tenants from database", error=str(e))
            # Continue with empty tenant list for in-memory fallback
            
    async def _start_background_tasks(self) -> None:
        """Start background cleanup and maintenance tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
    async def _cleanup_loop(self) -> None:
        """Background loop for tenant maintenance."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Reset usage counters
                await self._reset_usage_counters()
                
                # Cleanup inactive tenants
                await self._cleanup_inactive_tenants()
                
                # Persist tenant data
                await self._persist_tenants()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Tenant cleanup loop error", error=str(e))
                
    async def _reset_usage_counters(self) -> None:
        """Reset usage counters based on time periods."""
        import time
        current_time = time.time()
        
        for tenant in self._tenants.values():
            # Reset hourly counters
            if current_time - tenant.usage.hour_reset >= 3600:
                tenant.usage.requests_this_hour = 0
                tenant.usage.hour_reset = current_time
                
            # Reset daily counters
            if current_time - tenant.usage.day_reset >= 86400:
                tenant.usage.requests_this_day = 0
                tenant.usage.jobs_this_day = 0
                tenant.usage.day_reset = current_time
                
            # Reset monthly counters  
            if current_time - tenant.usage.month_reset >= 2592000:
                tenant.usage.requests_this_month = 0
                tenant.usage.month_reset = current_time
                
    async def _cleanup_inactive_tenants(self) -> None:
        """Mark inactive tenants for cleanup."""
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        for tenant in self._tenants.values():
            if (tenant.config.last_activity and 
                tenant.config.last_activity < cutoff_date and
                tenant.config.status == TenantStatus.ACTIVE):
                
                tenant.config.status = TenantStatus.INACTIVE
                logger.info(f"Marked tenant {tenant.tenant_id} as inactive")
                
    async def _persist_tenants(self) -> None:
        """Persist tenant data to database."""
        try:
            from ...database import get_database_manager
            
            db = get_database_manager()
            
            for tenant in self._tenants.values():
                await self._save_tenant_to_db(db, tenant)
                
        except Exception as e:
            logger.warning("Failed to persist tenant data", error=str(e))
            
    async def _save_tenant_to_db(self, db, tenant: TenantModel) -> None:
        """Save single tenant to database."""
        tenant_data = tenant.to_dict()
        
        await db.execute("""
            INSERT OR REPLACE INTO tenants (
                tenant_id, config, quotas, usage, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, [
            tenant.tenant_id,
            tenant_data["config"],
            tenant_data["quotas"], 
            tenant_data["usage"],
            tenant.config.created_at.isoformat(),
            datetime.utcnow().isoformat()
        ])
        
    async def create_tenant(
        self,
        name: str,
        contact_email: str,
        plan: TenantPlan = TenantPlan.FREE,
        **kwargs
    ) -> TenantModel:
        """Create a new tenant."""
        try:
            tenant = TenantModel.create_new(
                name=name,
                contact_email=contact_email,
                plan=plan,
                **kwargs
            )
            
            # Store tenant
            self._tenants[tenant.tenant_id] = tenant
            
            # Persist to database
            try:
                from ...database import get_database_manager
                db = get_database_manager()
                await self._save_tenant_to_db(db, tenant)
            except Exception as e:
                logger.warning("Failed to persist new tenant", error=str(e))
                
            logger.info(f"Created tenant {tenant.tenant_id}", name=name, plan=plan.value)
            return tenant
            
        except Exception as e:
            logger.error("Failed to create tenant", error=str(e), name=name)
            raise
            
    async def get_tenant(self, tenant_id: str) -> Optional[TenantModel]:
        """Get tenant by ID."""
        return self._tenants.get(tenant_id)
        
    async def get_tenant_by_api_key(self, api_key: str) -> Optional[TenantModel]:
        """Get tenant by API key."""
        tenant_id = self._api_key_to_tenant.get(api_key)
        if tenant_id:
            return await self.get_tenant(tenant_id)
        return None
        
    async def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        plan: Optional[TenantPlan] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[TenantModel]:
        """List tenants with optional filtering."""
        tenants = list(self._tenants.values())
        
        # Apply filters
        if status:
            tenants = [t for t in tenants if t.config.status == status]
        if plan:
            tenants = [t for t in tenants if t.config.plan == plan]
            
        # Apply pagination
        if limit:
            tenants = tenants[offset:offset + limit]
        elif offset:
            tenants = tenants[offset:]
            
        return tenants
        
    async def update_tenant(
        self,
        tenant_id: str,
        **updates
    ) -> Optional[TenantModel]:
        """Update tenant configuration."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None
            
        try:
            # Update config fields
            for key, value in updates.items():
                if hasattr(tenant.config, key):
                    setattr(tenant.config, key, value)
                    
            tenant.config.updated_at = datetime.utcnow()
            
            # Persist changes
            try:
                from ...database import get_database_manager
                db = get_database_manager()
                await self._save_tenant_to_db(db, tenant)
            except Exception as e:
                logger.warning("Failed to persist tenant update", error=str(e))
                
            logger.info(f"Updated tenant {tenant_id}")
            return tenant
            
        except Exception as e:
            logger.error("Failed to update tenant", error=str(e), tenant_id=tenant_id)
            raise
            
    async def update_tenant_plan(
        self,
        tenant_id: str,
        new_plan: TenantPlan
    ) -> Optional[TenantModel]:
        """Update tenant subscription plan."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None
            
        try:
            # Update plan
            old_plan = tenant.config.plan
            tenant.config.plan = new_plan
            tenant.config.updated_at = datetime.utcnow()
            
            # Update quotas for new plan
            tenant.quotas = tenant._default_quotas_for_plan(new_plan)
            
            # Persist changes
            try:
                from ...database import get_database_manager
                db = get_database_manager()
                await self._save_tenant_to_db(db, tenant)
            except Exception as e:
                logger.warning("Failed to persist plan update", error=str(e))
                
            logger.info(
                f"Updated tenant plan",
                tenant_id=tenant_id,
                old_plan=old_plan.value,
                new_plan=new_plan.value
            )
            return tenant
            
        except Exception as e:
            logger.error("Failed to update tenant plan", error=str(e))
            raise
            
    async def suspend_tenant(self, tenant_id: str, reason: str = "") -> Optional[TenantModel]:
        """Suspend a tenant."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None
            
        tenant.config.status = TenantStatus.SUSPENDED
        tenant.config.updated_at = datetime.utcnow()
        
        logger.info(f"Suspended tenant {tenant_id}", reason=reason)
        return tenant
        
    async def reactivate_tenant(self, tenant_id: str) -> Optional[TenantModel]:
        """Reactivate a suspended tenant."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None
            
        tenant.config.status = TenantStatus.ACTIVE
        tenant.config.updated_at = datetime.utcnow()
        
        logger.info(f"Reactivated tenant {tenant_id}")
        return tenant
        
    async def delete_tenant(self, tenant_id: str) -> bool:
        """Mark tenant for deletion."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
            
        tenant.config.status = TenantStatus.DELETED
        tenant.config.updated_at = datetime.utcnow()
        
        # Remove from active tenants
        del self._tenants[tenant_id]
        
        logger.info(f"Deleted tenant {tenant_id}")
        return True
        
    async def register_api_key(self, api_key: str, tenant_id: str) -> None:
        """Register API key to tenant mapping."""
        self._api_key_to_tenant[api_key] = tenant_id
        
    async def unregister_api_key(self, api_key: str) -> None:
        """Unregister API key."""
        if api_key in self._api_key_to_tenant:
            del self._api_key_to_tenant[api_key]
            
    async def get_tenant_usage_stats(self) -> Dict[str, Any]:
        """Get overall tenant usage statistics."""
        stats = {
            "total_tenants": len(self._tenants),
            "active_tenants": 0,
            "suspended_tenants": 0,
            "inactive_tenants": 0,
            "by_plan": {},
            "total_requests_today": 0,
            "total_active_jobs": 0,
            "total_storage_used_mb": 0.0
        }
        
        for tenant in self._tenants.values():
            # Count by status
            if tenant.config.status == TenantStatus.ACTIVE:
                stats["active_tenants"] += 1
            elif tenant.config.status == TenantStatus.SUSPENDED:
                stats["suspended_tenants"] += 1
            elif tenant.config.status == TenantStatus.INACTIVE:
                stats["inactive_tenants"] += 1
                
            # Count by plan
            plan_name = tenant.config.plan.value
            stats["by_plan"][plan_name] = stats["by_plan"].get(plan_name, 0) + 1
            
            # Aggregate usage
            stats["total_requests_today"] += tenant.usage.requests_this_day
            stats["total_active_jobs"] += tenant.usage.active_jobs
            stats["total_storage_used_mb"] += tenant.usage.storage_used_mb
            
        return stats
        
    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
                
        # Final persist
        await self._persist_tenants()
        
        self._tenants.clear()
        self._api_key_to_tenant.clear()
        self._initialized = False
        
        logger.info("Tenant manager cleaned up")


# Global tenant manager instance
_tenant_manager: Optional[TenantManager] = None


async def get_tenant_manager() -> TenantManager:
    """Get global tenant manager instance."""
    global _tenant_manager
    
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
        await _tenant_manager.initialize()
        
    return _tenant_manager