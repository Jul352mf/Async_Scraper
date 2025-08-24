"""
Proxy support module for Async_Scraper.

Provides comprehensive proxy management including configuration, rotation,
health checking, and integration with HTTP clients and browsers.
"""

from .manager import ProxyManager
from .models import Proxy, ProxyConfig, ProxyRotationStrategy, ProxyHealth
from .rotation import ProxyRotator
from .health_checker import ProxyHealthChecker

__all__ = [
    "ProxyManager",
    "Proxy", 
    "ProxyConfig",
    "ProxyRotationStrategy",
    "ProxyHealth",
    "ProxyRotator",
    "ProxyHealthChecker",
]