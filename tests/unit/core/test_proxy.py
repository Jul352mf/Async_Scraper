"""
Unit tests for the proxy system.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from scraper.core.proxy.models import Proxy, ProxyConfig, ProxyRotationStrategy, ProxyType, ProxyStatus
from scraper.core.proxy.rotation import ProxyRotator, RoundRobinRotator
from scraper.core.proxy.health_checker import ProxyHealthChecker
from scraper.core.proxy.manager import ProxyManager


class TestProxyModels:
    """Test proxy model functionality."""
    
    def test_proxy_creation_from_url(self):
        """Test creating proxy from URL."""
        proxy = Proxy(url="http://proxy.example.com:8080")
        
        assert proxy.host == "proxy.example.com"
        assert proxy.port == 8080
        assert proxy.proxy_type == ProxyType.HTTP
        assert proxy.enabled is True
    
    def test_proxy_with_auth(self):
        """Test proxy with authentication."""
        proxy = Proxy(
            url="socks5://user:pass@proxy.example.com:1080",
            username="user",
            password="pass"
        )
        
        assert proxy.host == "proxy.example.com"
        assert proxy.port == 1080
        assert proxy.proxy_type == ProxyType.SOCKS5
        assert proxy.username == "user"
        assert proxy.password == "pass"
    
    def test_proxy_to_dict(self):
        """Test converting proxy to dictionary."""
        proxy = Proxy(
            url="http://user:pass@proxy.example.com:8080",
            username="user",
            password="pass"
        )
        
        # Without credentials
        proxy_dict = proxy.to_dict(include_credentials=False)
        assert proxy_dict["server"] == "http://proxy.example.com:8080"
        assert "username" not in proxy_dict
        assert "password" not in proxy_dict
        
        # With credentials
        proxy_dict = proxy.to_dict(include_credentials=True)
        assert proxy_dict["server"] == "http://proxy.example.com:8080"
        assert proxy_dict["username"] == "user"
        assert proxy_dict["password"] == "pass"
    
    def test_proxy_health_tracking(self):
        """Test proxy health tracking."""
        proxy = Proxy(url="http://proxy.example.com:8080")
        
        # Initial state
        assert proxy.health.status == ProxyStatus.UNKNOWN
        assert proxy.health.success_rate == 0.0
        assert proxy.health.is_healthy is False
        
        # Record successes
        proxy.update_health(success=True, response_time=0.5)
        proxy.update_health(success=True, response_time=0.3)
        
        assert proxy.health.status == ProxyStatus.HEALTHY
        assert proxy.health.success_count == 2
        assert proxy.health.consecutive_failures == 0
        assert proxy.health.success_rate == 100.0
        assert proxy.health.is_healthy is True
        
        # Record failure
        proxy.update_health(success=False, error="Connection failed")
        
        assert round(proxy.health.success_rate, 2) == 66.67  # 2 successes out of 3 total
        assert proxy.health.consecutive_failures == 1
        assert proxy.health.error_message == "Connection failed"


class TestProxyRotation:
    """Test proxy rotation strategies."""
    
    def setup_method(self):
        """Setup test proxies."""
        self.proxies = [
            Proxy(url="http://proxy1.example.com:8080"),
            Proxy(url="http://proxy2.example.com:8080"),
            Proxy(url="http://proxy3.example.com:8080"),
        ]
        
        # Mark all as healthy
        for proxy in self.proxies:
            proxy.update_health(success=True)
    
    def test_round_robin_rotation(self):
        """Test round-robin rotation strategy."""
        rotator = ProxyRotator(self.proxies, ProxyRotationStrategy.ROUND_ROBIN)
        
        # Should cycle through proxies
        first = rotator.get_next_proxy()
        second = rotator.get_next_proxy()
        third = rotator.get_next_proxy()
        fourth = rotator.get_next_proxy()  # Should wrap around
        
        assert first == self.proxies[0]
        assert second == self.proxies[1]
        assert third == self.proxies[2]
        assert fourth == self.proxies[0]  # Wrapped around
    
    def test_random_rotation(self):
        """Test random rotation strategy."""
        rotator = ProxyRotator(self.proxies, ProxyRotationStrategy.RANDOM)
        
        # Get several proxies to ensure randomness (all should be from our list)
        selected_proxies = [rotator.get_next_proxy() for _ in range(10)]
        
        assert all(proxy in self.proxies for proxy in selected_proxies)
        assert len(set(proxy.id for proxy in selected_proxies)) > 1  # Should have variety
    
    def test_least_used_rotation(self):
        """Test least used rotation strategy."""
        # Mark one proxy as more used
        self.proxies[0].use_count = 5
        self.proxies[1].use_count = 2
        self.proxies[2].use_count = 0
        
        rotator = ProxyRotator(self.proxies, ProxyRotationStrategy.LEAST_USED)
        
        # Should select least used proxy first
        selected = rotator.get_next_proxy()
        assert selected == self.proxies[2]  # use_count = 0
    
    def test_fastest_rotation(self):
        """Test fastest rotation strategy."""
        # Set response times
        self.proxies[0].health.response_time = 1.0
        self.proxies[1].health.response_time = 0.5
        self.proxies[2].health.response_time = 0.8
        
        rotator = ProxyRotator(self.proxies, ProxyRotationStrategy.FASTEST)
        
        # Should select fastest proxy
        selected = rotator.get_next_proxy()
        assert selected == self.proxies[1]  # response_time = 0.5
    
    def test_geographic_rotation(self):
        """Test geographic rotation strategy."""
        # Set countries
        self.proxies[0].country = "US"
        self.proxies[1].country = "UK"
        self.proxies[2].country = "US"
        
        rotator = ProxyRotator(self.proxies, ProxyRotationStrategy.GEOGRAPHIC)
        rotator.set_geographic_preference("US")
        
        # Should prefer US proxies
        selected_proxies = [rotator.get_next_proxy() for _ in range(5)]
        us_proxies = [p for p in selected_proxies if p.country == "US"]
        
        # Should have at least some US proxies (not guaranteed all due to randomness)
        assert len(us_proxies) > 0
    
    def test_unhealthy_proxy_filtering(self):
        """Test that unhealthy proxies are filtered out."""
        # Mark one proxy as unhealthy
        self.proxies[1].update_health(success=False)
        self.proxies[1].update_health(success=False)
        self.proxies[1].update_health(success=False)  # 3 consecutive failures
        
        rotator = ProxyRotator(self.proxies, ProxyRotationStrategy.ROUND_ROBIN)
        
        # Should only get healthy proxies
        selected_proxies = [rotator.get_next_proxy() for _ in range(10)]
        assert all(proxy in [self.proxies[0], self.proxies[2]] for proxy in selected_proxies)
        assert self.proxies[1] not in selected_proxies


@pytest.mark.asyncio
class TestProxyHealthChecker:
    """Test proxy health checking."""
    
    def setup_method(self):
        """Setup test environment."""
        config = ProxyConfig()
        self.health_checker = ProxyHealthChecker(config)
        self.proxy = Proxy(url="http://proxy.example.com:8080")
    
    @patch('aiohttp.ClientSession.get')
    async def test_successful_health_check(self, mock_get):
        """Test successful proxy health check."""
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_get.return_value.__aenter__.return_value = mock_response
        
        success = await self.health_checker.check_proxy(self.proxy)
        
        assert success is True
        assert self.proxy.health.status == ProxyStatus.HEALTHY
        assert self.proxy.health.success_count == 1
        assert self.proxy.health.consecutive_failures == 0
    
    @patch('aiohttp.ClientSession.get')
    async def test_failed_health_check(self, mock_get):
        """Test failed proxy health check."""
        # Mock HTTP error response
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_get.return_value.__aenter__.return_value = mock_response
        
        success = await self.health_checker.check_proxy(self.proxy)
        
        assert success is False
        assert self.proxy.health.status == ProxyStatus.UNHEALTHY
        assert self.proxy.health.failure_count == 1
        assert self.proxy.health.consecutive_failures == 1
    
    @patch('scraper.core.proxy.health_checker.ProxyHealthChecker._perform_health_check')
    async def test_health_check_exception(self, mock_perform_check):
        """Test health check with network exception."""
        # Mock network exception in the health check method
        mock_perform_check.side_effect = Exception("Network error")
        
        success = await self.health_checker.check_proxy(self.proxy)
        
        assert success is False
        assert self.proxy.health.status == ProxyStatus.UNHEALTHY
        assert self.proxy.health.error_message == "Network error"
    
    async def test_multiple_proxy_health_check(self):
        """Test checking multiple proxies concurrently."""
        proxies = [
            Proxy(url="http://proxy1.example.com:8080"),
            Proxy(url="http://proxy2.example.com:8080"),
            Proxy(url="http://proxy3.example.com:8080"),
        ]
        
        with patch.object(self.health_checker, 'check_proxy') as mock_check:
            mock_check.side_effect = [True, False, True]  # Mixed results
            
            results = await self.health_checker.check_proxies(proxies)
            
            assert len(results) == 3
            assert list(results.values()) == [True, False, True]


@pytest.mark.asyncio
class TestProxyManager:
    """Test proxy manager functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.config = ProxyConfig(enabled=True)
        self.manager = ProxyManager(self.config)
    
    async def test_proxy_manager_initialization(self):
        """Test proxy manager initialization."""
        await self.manager.initialize()
        assert self.manager._initialized is True
        
        await self.manager.shutdown()
        assert self.manager._initialized is False
    
    def test_add_and_list_proxies(self):
        """Test adding and listing proxies."""
        proxy1 = Proxy(url="http://proxy1.example.com:8080")
        proxy2 = Proxy(url="http://proxy2.example.com:8080")
        
        self.manager.add_proxy(proxy1)
        self.manager.add_proxy(proxy2)
        
        proxies = self.manager.list_proxies()
        assert len(proxies) == 2
        assert proxy1 in proxies
        assert proxy2 in proxies
    
    def test_enable_disable_proxy(self):
        """Test enabling and disabling proxies."""
        proxy = Proxy(url="http://proxy.example.com:8080")
        self.manager.add_proxy(proxy)
        
        # Disable proxy
        success = self.manager.disable_proxy(proxy.id)
        assert success is True
        assert proxy.enabled is False
        
        # Enable proxy
        success = self.manager.enable_proxy(proxy.id)
        assert success is True
        assert proxy.enabled is True
    
    def test_remove_proxy(self):
        """Test removing proxies."""
        proxy = Proxy(url="http://proxy.example.com:8080")
        self.manager.add_proxy(proxy)
        
        # Remove proxy
        success = self.manager.remove_proxy(proxy.id)
        assert success is True
        assert self.manager.get_proxy(proxy.id) is None
        
        # Try to remove non-existent proxy
        success = self.manager.remove_proxy("non-existent")
        assert success is False
    
    def test_update_proxy(self):
        """Test updating proxy configuration."""
        proxy = Proxy(url="http://proxy.example.com:8080")
        self.manager.add_proxy(proxy)
        
        updates = {
            "description": "Test proxy",
            "country": "US",
            "tags": ["fast", "reliable"]
        }
        
        success = self.manager.update_proxy(proxy.id, updates)
        assert success is True
        assert proxy.description == "Test proxy"
        assert proxy.country == "US"
        assert proxy.tags == ["fast", "reliable"]
    
    async def test_get_next_proxy(self):
        """Test getting next proxy with rotation."""
        proxy1 = Proxy(url="http://proxy1.example.com:8080")
        proxy2 = Proxy(url="http://proxy2.example.com:8080")
        
        # Mark both as healthy
        proxy1.update_health(success=True)
        proxy2.update_health(success=True)
        
        self.manager.add_proxies([proxy1, proxy2])
        
        # Get next proxy
        selected = await self.manager.get_next_proxy()
        assert selected in [proxy1, proxy2]
        assert selected.use_count == 1  # Should be marked as used
    
    def test_proxy_stats(self):
        """Test getting proxy statistics."""
        proxy1 = Proxy(url="http://proxy1.example.com:8080")
        proxy2 = Proxy(url="http://proxy2.example.com:8080")
        
        # Set up different health states
        proxy1.update_health(success=True, response_time=0.5)
        proxy2.update_health(success=False, error="Failed")
        proxy2.enabled = False
        
        self.manager.add_proxies([proxy1, proxy2])
        
        stats = self.manager.get_proxy_stats()
        
        assert stats["total_proxies"] == 2
        assert stats["enabled_proxies"] == 1
        assert stats["healthy_proxies"] == 1
        assert stats["rotation_strategy"] == "round_robin"
    
    def test_create_from_urls(self):
        """Test creating proxy manager from URL list."""
        urls = [
            "http://proxy1.example.com:8080",
            "socks5://user:pass@proxy2.example.com:1080",
            "invalid-url"  # Should be skipped
        ]
        
        manager = ProxyManager.from_urls(urls, self.config)
        proxies = manager.list_proxies()
        
        assert len(proxies) == 2  # Invalid URL should be skipped
        assert any(p.host == "proxy1.example.com" for p in proxies)
        assert any(p.host == "proxy2.example.com" for p in proxies)