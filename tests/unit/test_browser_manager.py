"""
Unit tests for the browser manager.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from scraper.services.browser_manager import (
    BrowserManager, 
    BrowserPool, 
    BrowserType, 
    BrowserInstance,
    get_browser_manager,
    cleanup_browser_manager
)
from scraper.core.config import Config, BrowserConfig


class TestBrowserPool:
    """Test browser pool functionality."""
    
    @pytest.fixture
    def browser_pool(self):
        """Create a browser pool for testing."""
        return BrowserPool(max_browsers=2, max_contexts_per_browser=3)
    
    @pytest.mark.asyncio
    async def test_browser_pool_start_stop(self, browser_pool):
        """Test browser pool startup and shutdown."""
        # Start pool
        with patch('scraper.services.browser_manager.async_playwright') as mock_playwright:
            mock_playwright.return_value.start = AsyncMock()
            
            await browser_pool.start()
            
            assert browser_pool._playwright is not None
            mock_playwright.return_value.start.assert_called_once()
        
        # Stop pool
        with patch.object(browser_pool, '_playwright') as mock_playwright_instance:
            mock_playwright_instance.stop = AsyncMock()
            
            await browser_pool.stop()
            
            mock_playwright_instance.stop.assert_called_once()
            assert browser_pool._playwright is None
    
    @pytest.mark.asyncio
    async def test_get_browser_creates_new_browser(self, browser_pool):
        """Test that get_browser creates a new browser when pool is empty."""
        with patch.object(browser_pool, '_create_browser') as mock_create:
            mock_browser = AsyncMock()
            mock_create.return_value = mock_browser
            
            # Mock playwright start
            browser_pool._playwright = MagicMock()
            
            browser = await browser_pool.get_browser(BrowserType.CHROMIUM)
            
            assert browser == mock_browser
            assert len(browser_pool.browsers) == 1
            mock_create.assert_called_once_with(BrowserType.CHROMIUM)
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_browsers(self, browser_pool):
        """Test cleanup of stale browsers."""
        # Create mock browser instance
        mock_browser = AsyncMock()
        mock_browser.close = AsyncMock()
        
        # Add stale browser to pool
        import time
        old_time = time.time() - 4000  # 4000 seconds ago
        
        browser_pool.browsers["stale_browser"] = BrowserInstance(
            browser=mock_browser,
            browser_type=BrowserType.CHROMIUM,
            created_at=old_time,
            contexts=[]
        )
        
        # Run cleanup
        await browser_pool.cleanup_stale_browsers(max_age_seconds=3600)
        
        # Verify browser was closed and removed
        mock_browser.close.assert_called_once()
        assert "stale_browser" not in browser_pool.browsers


class TestBrowserManager:
    """Test browser manager functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = Config()
        config.browser = BrowserConfig(
            max_browsers=2,
            max_contexts_per_browser=3,
            viewport_width=1920,
            viewport_height=1080,
            timeout=60.0,
            load_images=False
        )
        return config
    
    @pytest.fixture
    def browser_manager(self, mock_config):
        """Create browser manager for testing."""
        with patch('scraper.services.browser_manager.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            return BrowserManager()
    
    @pytest.mark.asyncio
    async def test_browser_manager_start_stop(self, browser_manager):
        """Test browser manager startup and shutdown."""
        with patch.object(browser_manager.pool, 'start') as mock_start:
            await browser_manager.start()
            mock_start.assert_called_once()
            assert browser_manager._cleanup_task is not None
        
        with patch.object(browser_manager.pool, 'stop') as mock_stop:
            await browser_manager.stop()
            mock_stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_page_content_success(self, browser_manager):
        """Test successful page content retrieval."""
        mock_page = AsyncMock()
        mock_page.goto.return_value = AsyncMock(status=200)
        mock_page.content.return_value = "<html><body>Test content</body></html>"
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.route = AsyncMock()
        mock_page.close = AsyncMock()
        
        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_context.close = AsyncMock()
        
        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        
        with patch.object(browser_manager.pool, 'get_browser') as mock_get_browser:
            mock_get_browser.return_value = mock_browser
            
            content = await browser_manager.get_page_content("https://example.com")
            
            assert content == "<html><body>Test content</body></html>"
            mock_page.goto.assert_called_once()
            mock_page.content.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_page_content_failure(self, browser_manager):
        """Test page content retrieval failure."""
        mock_page = AsyncMock()
        mock_page.goto.return_value = AsyncMock(status=404)
        mock_page.close = AsyncMock()
        
        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_context.close = AsyncMock()
        
        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        
        with patch.object(browser_manager.pool, 'get_browser') as mock_get_browser:
            mock_get_browser.return_value = mock_browser
            
            content = await browser_manager.get_page_content("https://example.com")
            
            assert content is None
    
    @pytest.mark.asyncio
    async def test_take_screenshot(self, browser_manager):
        """Test screenshot functionality."""
        mock_page = AsyncMock()
        mock_page.goto.return_value = AsyncMock(status=200)
        mock_page.screenshot = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.close = AsyncMock()
        
        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_context.close = AsyncMock()
        
        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        
        with patch.object(browser_manager.pool, 'get_browser') as mock_get_browser:
            mock_get_browser.return_value = mock_browser
            
            result = await browser_manager.take_screenshot(
                "https://example.com", 
                "screenshot.png"
            )
            
            assert result is True
            mock_page.screenshot.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_dynamic_emails(self, browser_manager):
        """Test dynamic email extraction."""
        mock_emails = ["test@example.com", "contact@example.com"]
        
        mock_page = AsyncMock()
        mock_page.goto.return_value = AsyncMock(status=200)
        mock_page.evaluate.return_value = mock_emails
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.close = AsyncMock()
        
        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_context.close = AsyncMock()
        
        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        
        with patch.object(browser_manager.pool, 'get_browser') as mock_get_browser:
            mock_get_browser.return_value = mock_browser
            
            emails = await browser_manager.extract_dynamic_emails("https://example.com")
            
            assert emails == mock_emails
            mock_page.evaluate.assert_called_once()


class TestGlobalBrowserManager:
    """Test global browser manager functions."""
    
    @pytest.mark.asyncio
    async def test_get_browser_manager_singleton(self):
        """Test that get_browser_manager returns singleton instance."""
        # Clean up any existing instance
        await cleanup_browser_manager()
        
        with patch('scraper.services.browser_manager.BrowserManager') as mock_manager_class:
            mock_instance = AsyncMock()
            mock_instance.start = AsyncMock()
            mock_manager_class.return_value = mock_instance
            
            # First call should create instance
            manager1 = await get_browser_manager()
            assert manager1 == mock_instance
            mock_instance.start.assert_called_once()
            
            # Second call should return same instance
            manager2 = await get_browser_manager()
            assert manager2 == manager1
            assert manager2 == mock_instance
    
    @pytest.mark.asyncio
    async def test_cleanup_browser_manager(self):
        """Test cleanup of global browser manager."""
        with patch('scraper.services.browser_manager.BrowserManager') as mock_manager_class:
            mock_instance = AsyncMock()
            mock_instance.start = AsyncMock()
            mock_instance.stop = AsyncMock()
            mock_manager_class.return_value = mock_instance
            
            # Create manager
            await get_browser_manager()
            
            # Cleanup
            await cleanup_browser_manager()
            
            mock_instance.stop.assert_called_once()


class TestBrowserType:
    """Test browser type enum."""
    
    def test_browser_type_values(self):
        """Test browser type enum values."""
        assert BrowserType.CHROMIUM.value == "chromium"
        assert BrowserType.FIREFOX.value == "firefox"
        assert BrowserType.WEBKIT.value == "webkit"


class TestBrowserInstance:
    """Test browser instance dataclass."""
    
    def test_browser_instance_creation(self):
        """Test browser instance creation."""
        mock_browser = MagicMock()
        instance = BrowserInstance(
            browser=mock_browser,
            browser_type=BrowserType.CHROMIUM,
            created_at=1234567890.0,
            contexts=[],
            active_pages=0
        )
        
        assert instance.browser == mock_browser
        assert instance.browser_type == BrowserType.CHROMIUM
        assert instance.created_at == 1234567890.0
        assert instance.contexts == []
        assert instance.active_pages == 0