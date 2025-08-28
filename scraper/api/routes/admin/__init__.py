"""Admin API endpoints."""

from .tenants import router as tenants_router
from .monitoring import router as monitoring_router
from .system import router as system_router

__all__ = ["tenants_router", "monitoring_router", "system_router"]