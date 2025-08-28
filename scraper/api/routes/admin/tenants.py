"""Tenant management API endpoints."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel, Field

from ....core.tenant import get_tenant_manager, TenantModel, TenantPlan, TenantStatus
from ....core.tenant.middleware import require_tenant
from ....core.logger import get_logger
from ....core.monitoring import metrics_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/tenants", tags=["admin", "tenants"])


class CreateTenantRequest(BaseModel):
    """Request model for creating a tenant."""
    
    name: str = Field(..., description="Tenant name")
    contact_email: str = Field(..., description="Contact email")
    organization: Optional[str] = Field(None, description="Organization name")
    plan: TenantPlan = Field(TenantPlan.FREE, description="Subscription plan")
    description: Optional[str] = Field(None, description="Tenant description")
    custom_domain: Optional[str] = Field(None, description="Custom domain")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    tags: List[str] = Field(default_factory=list, description="Tags")


class UpdateTenantRequest(BaseModel):
    """Request model for updating a tenant."""
    
    name: Optional[str] = Field(None, description="Tenant name")
    contact_email: Optional[str] = Field(None, description="Contact email")
    organization: Optional[str] = Field(None, description="Organization name")
    description: Optional[str] = Field(None, description="Tenant description")
    custom_domain: Optional[str] = Field(None, description="Custom domain")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    tags: Optional[List[str]] = Field(None, description="Tags")
    status: Optional[TenantStatus] = Field(None, description="Tenant status")


class TenantResponse(BaseModel):
    """Response model for tenant data."""
    
    tenant_id: str
    config: Dict[str, Any]
    quotas: Dict[str, Any]
    usage: Dict[str, Any]
    usage_percentage: Dict[str, float]


@router.post("/", response_model=TenantResponse)
async def create_tenant(request: CreateTenantRequest) -> TenantResponse:
    """Create a new tenant."""
    try:
        tenant_manager = await get_tenant_manager()
        
        tenant = await tenant_manager.create_tenant(
            name=request.name,
            contact_email=request.contact_email,
            plan=request.plan,
            organization=request.organization,
            description=request.description,
            custom_domain=request.custom_domain,
            webhook_url=request.webhook_url,
            tags=request.tags
        )
        
        # Record metrics
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "create_tenant", "status": "success"}
        )
        
        return TenantResponse(**tenant.to_dict())
        
    except Exception as e:
        logger.error("Failed to create tenant", error=str(e))
        
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "create_tenant", "status": "error"}
        )
        
        raise HTTPException(status_code=500, detail="Failed to create tenant")


@router.get("/", response_model=List[TenantResponse])
async def list_tenants(
    status: Optional[TenantStatus] = Query(None, description="Filter by status"),
    plan: Optional[TenantPlan] = Query(None, description="Filter by plan"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit results"),
    offset: int = Query(0, ge=0, description="Offset results")
) -> List[TenantResponse]:
    """List tenants with optional filtering."""
    try:
        tenant_manager = await get_tenant_manager()
        
        tenants = await tenant_manager.list_tenants(
            status=status,
            plan=plan,
            limit=limit,
            offset=offset
        )
        
        return [TenantResponse(**tenant.to_dict()) for tenant in tenants]
        
    except Exception as e:
        logger.error("Failed to list tenants", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list tenants")


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str) -> TenantResponse:
    """Get tenant by ID."""
    try:
        tenant_manager = await get_tenant_manager()
        
        tenant = await tenant_manager.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
            
        return TenantResponse(**tenant.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tenant", error=str(e), tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail="Failed to get tenant")


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str, 
    request: UpdateTenantRequest
) -> TenantResponse:
    """Update tenant configuration."""
    try:
        tenant_manager = await get_tenant_manager()
        
        # Filter out None values
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
            
        tenant = await tenant_manager.update_tenant(tenant_id, **updates)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
            
        # Record metrics
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "update_tenant", "status": "success"}
        )
        
        return TenantResponse(**tenant.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update tenant", error=str(e), tenant_id=tenant_id)
        
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "update_tenant", "status": "error"}
        )
        
        raise HTTPException(status_code=500, detail="Failed to update tenant")


@router.post("/{tenant_id}/plan")
async def update_tenant_plan(
    tenant_id: str,
    new_plan: TenantPlan
) -> TenantResponse:
    """Update tenant subscription plan."""
    try:
        tenant_manager = await get_tenant_manager()
        
        tenant = await tenant_manager.update_tenant_plan(tenant_id, new_plan)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
            
        # Record metrics
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "update_plan", "status": "success"}
        )
        
        return TenantResponse(**tenant.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update tenant plan", error=str(e), tenant_id=tenant_id)
        
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "update_plan", "status": "error"}
        )
        
        raise HTTPException(status_code=500, detail="Failed to update tenant plan")


@router.post("/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: str,
    reason: Optional[str] = None
) -> TenantResponse:
    """Suspend a tenant."""
    try:
        tenant_manager = await get_tenant_manager()
        
        tenant = await tenant_manager.suspend_tenant(tenant_id, reason or "")
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
            
        # Record metrics
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "suspend_tenant", "status": "success"}
        )
        
        return TenantResponse(**tenant.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to suspend tenant", error=str(e), tenant_id=tenant_id)
        
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "suspend_tenant", "status": "error"}
        )
        
        raise HTTPException(status_code=500, detail="Failed to suspend tenant")


@router.post("/{tenant_id}/reactivate")
async def reactivate_tenant(tenant_id: str) -> TenantResponse:
    """Reactivate a suspended tenant."""
    try:
        tenant_manager = await get_tenant_manager()
        
        tenant = await tenant_manager.reactivate_tenant(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
            
        # Record metrics
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "reactivate_tenant", "status": "success"}
        )
        
        return TenantResponse(**tenant.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reactivate tenant", error=str(e), tenant_id=tenant_id)
        
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "reactivate_tenant", "status": "error"}
        )
        
        raise HTTPException(status_code=500, detail="Failed to reactivate tenant")


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str) -> Dict[str, str]:
    """Delete a tenant."""
    try:
        tenant_manager = await get_tenant_manager()
        
        success = await tenant_manager.delete_tenant(tenant_id)
        if not success:
            raise HTTPException(status_code=404, detail="Tenant not found")
            
        # Record metrics
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "delete_tenant", "status": "success"}
        )
        
        return {"message": "Tenant deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete tenant", error=str(e), tenant_id=tenant_id)
        
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "delete_tenant", "status": "error"}
        )
        
        raise HTTPException(status_code=500, detail="Failed to delete tenant")


@router.get("/{tenant_id}/usage")
async def get_tenant_usage(tenant_id: str) -> Dict[str, Any]:
    """Get detailed tenant usage information."""
    try:
        tenant_manager = await get_tenant_manager()
        
        tenant = await tenant_manager.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
            
        # Get additional usage stats from database
        from ....core.tenant.isolation import TenantIsolationManager
        from ....database import get_database_manager
        
        isolation_manager = TenantIsolationManager()
        db = get_database_manager()
        
        storage_usage = await isolation_manager.get_tenant_storage_usage(db, tenant_id)
        
        return {
            **tenant.to_dict()["usage"],
            **storage_usage,
            "usage_percentage": tenant.get_usage_percentage(),
            "quotas": tenant.to_dict()["quotas"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tenant usage", error=str(e), tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail="Failed to get tenant usage")


@router.post("/{tenant_id}/cleanup")
async def cleanup_tenant_data(
    tenant_id: str,
    retention_days: int = Query(30, ge=1, le=365, description="Data retention in days")
) -> Dict[str, Any]:
    """Cleanup old tenant data."""
    try:
        tenant_manager = await get_tenant_manager()
        
        tenant = await tenant_manager.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
            
        # Perform cleanup
        from ....core.tenant.isolation import TenantIsolationManager
        from ....database import get_database_manager
        
        isolation_manager = TenantIsolationManager()
        db = get_database_manager()
        
        cleanup_stats = await isolation_manager.cleanup_tenant_data(
            db, tenant_id, retention_days
        )
        
        # Record metrics
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "cleanup_tenant", "status": "success"}
        )
        
        return {
            "message": "Tenant data cleanup completed",
            "retention_days": retention_days,
            "stats": cleanup_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cleanup tenant data", error=str(e), tenant_id=tenant_id)
        
        metrics_manager.increment_counter(
            "admin_operations_total",
            {"operation": "cleanup_tenant", "status": "error"}
        )
        
        raise HTTPException(status_code=500, detail="Failed to cleanup tenant data")