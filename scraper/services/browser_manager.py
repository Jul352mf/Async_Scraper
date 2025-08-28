"""
Browser Manager for Playwright Integration

This module manages browser instances, connection pools, and resource cleanup
for JavaScript content scraping.
"""

import asyncio
import contextlib
import time
from typing import Optional, Dict, Any, List, AsyncContextManager, Union
from dataclasses import dataclass
from enum import Enum
import structlog

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from scraper.core.config import get_config
from scraper.core.logger import get_logger
from scraper.core.proxy import ProxyManager

logger = get_logger(__name__)


class BrowserType(Enum):
    """Supported browser types."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


@dataclass
class BrowserInstance:
    """Represents a browser instance with metadata."""
    browser: Browser
    browser_type: BrowserType
    created_at: float
    contexts: List[BrowserContext]
    active_pages: int = 0


class BrowserPool:
    """Manages a pool of browser instances with resource limits."""
    
    def __init__(self, max_browsers: int = 3, max_contexts_per_browser: int = 10):
        self.max_browsers = max_browsers
        self.max_contexts_per_browser = max_contexts_per_browser
        self.browsers: Dict[str, BrowserInstance] = {}
        self._lock = asyncio.Lock()
        self._playwright: Optional[Playwright] = None
        
    async def start(self) -> None:
        """Start the browser pool."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()
            logger.info("Browser pool started", max_browsers=self.max_browsers)
    
    async def stop(self) -> None:
        """Stop the browser pool and cleanup all browsers."""
        async with self._lock:
            # Close all browsers
            for browser_id, instance in self.browsers.items():
                try:
                    await instance.browser.close()
                    logger.debug("Browser closed", browser_id=browser_id)
                except Exception as e:
                    logger.warning("Error closing browser", browser_id=browser_id, error=str(e))
            
            self.browsers.clear()
            
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
                
        logger.info("Browser pool stopped")
    
    async def get_browser(self, browser_type: BrowserType = BrowserType.CHROMIUM) -> Browser:
        """Get or create a browser instance."""
        if not self._playwright:
            await self.start()
        
        async with self._lock:
            # Check for existing browser of the same type
            for instance in self.browsers.values():
                if (instance.browser_type == browser_type and 
                    len(instance.contexts) < self.max_contexts_per_browser):
                    return instance.browser
            
            # Create new browser if under limit
            if len(self.browsers) < self.max_browsers:
                browser_id = f"{browser_type.value}_{len(self.browsers)}"
                browser = await self._create_browser(browser_type)
                
                self.browsers[browser_id] = BrowserInstance(
                    browser=browser,
                    browser_type=browser_type,
                    created_at=time.time(),
                    contexts=[]
                )
                
                logger.debug("New browser created", 
                           browser_id=browser_id, 
                           browser_type=browser_type.value)
                return browser
            
            # If pool is full, return least loaded browser
            least_loaded = min(self.browsers.values(), key=lambda x: len(x.contexts))
            return least_loaded.browser
    
    async def _create_browser(self, browser_type: BrowserType) -> Browser:
        """Create a new browser instance with configuration."""
        config = get_config()
        
        launch_options = {
            "headless": not config.browser.show_browser,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-images" if not config.browser.load_images else "",
                f"--window-size={config.browser.viewport_width},{config.browser.viewport_height}",
            ]
        }
        
        # Remove empty args
        launch_options["args"] = [arg for arg in launch_options["args"] if arg]
        
        if browser_type == BrowserType.CHROMIUM:
            return await self._playwright.chromium.launch(**launch_options)
        elif browser_type == BrowserType.FIREFOX:
            return await self._playwright.firefox.launch(**launch_options)
        elif browser_type == BrowserType.WEBKIT:
            return await self._playwright.webkit.launch(**launch_options)
        else:
            raise ValueError(f"Unsupported browser type: {browser_type}")
    
    async def cleanup_stale_browsers(self, max_age_seconds: int = 3600) -> None:
        """Clean up browsers that have been idle for too long."""
        current_time = time.time()
        stale_browsers = []
        
        async with self._lock:
            for browser_id, instance in self.browsers.items():
                if (current_time - instance.created_at > max_age_seconds and 
                    len(instance.contexts) == 0):
                    stale_browsers.append(browser_id)
            
            for browser_id in stale_browsers:
                instance = self.browsers[browser_id]
                try:
                    await instance.browser.close()
                    del self.browsers[browser_id]
                    logger.debug("Stale browser cleaned up", browser_id=browser_id)
                except Exception as e:
                    logger.warning("Error cleaning up stale browser", 
                                 browser_id=browser_id, error=str(e))


class BrowserManager:
    """High-level browser manager for scraping operations."""
    
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.config = get_config()
        self.pool = BrowserPool(
            max_browsers=self.config.browser.max_browsers,
            max_contexts_per_browser=self.config.browser.max_contexts_per_browser
        )
        self.proxy_manager = proxy_manager
        self._cleanup_task: Optional[asyncio.Task] = None
        
    async def start(self) -> None:
        """Start the browser manager."""
        await self.pool.start()
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info("Browser manager started")
    
    async def stop(self) -> None:
        """Stop the browser manager and cleanup resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        await self.pool.stop()
        logger.info("Browser manager stopped")
    
    @contextlib.asynccontextmanager
    async def get_page(
        self, 
        browser_type: BrowserType = BrowserType.CHROMIUM,
        context_options: Optional[Dict[str, Any]] = None
    ) -> AsyncContextManager[Page]:
        """Get a browser page with automatic cleanup and proxy support."""
        browser = await self.pool.get_browser(browser_type)
        
        # Create context with default options
        default_context_options = {
            "viewport": {
                "width": self.config.browser.viewport_width,
                "height": self.config.browser.viewport_height
            },
            "user_agent": self.config.scraping.user_agent,
            "ignore_https_errors": True,
            "java_script_enabled": True,
        }
        
        # Add proxy configuration if available
        if self.proxy_manager:
            proxy = await self.proxy_manager.get_next_proxy()
            if proxy:
                proxy_config = proxy.to_dict(include_credentials=True)
                default_context_options["proxy"] = proxy_config
                logger.debug("Using proxy for browser context", proxy_id=proxy.id, proxy_host=proxy.effective_host)
        
        if context_options:
            default_context_options.update(context_options)
        
        context = await browser.new_context(**default_context_options)
        page = await context.new_page()
        
        # Configure page
        page.set_default_timeout(self.config.browser.timeout * 1000)  # Convert to ms
        
        if not self.config.browser.load_images:
            await page.route("**/*.{png,jpg,jpeg,gif,svg}", lambda route: route.abort())
        
        try:
            yield page
        finally:
            try:
                await page.close()
                await context.close()
            except Exception as e:
                logger.warning("Error cleaning up page/context", error=str(e))
    
    async def get_page_content(
        self, 
        url: str, 
        wait_for_selector: Optional[str] = None,
        wait_for_timeout: Optional[int] = None,
        browser_type: BrowserType = BrowserType.CHROMIUM
    ) -> Optional[str]:
        """Get page content with JavaScript rendering."""
        try:
            async with self.get_page(browser_type=browser_type) as page:
                # Navigate to page
                response = await page.goto(url, wait_until="networkidle")
                
                if not response or response.status >= 400:
                    logger.warning("Failed to load page", url=url, status=response.status if response else None)
                    return None
                
                # Wait for specific selector if provided
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=wait_for_timeout or self.config.browser.timeout * 1000)
                    except Exception as e:
                        logger.warning("Selector wait failed", url=url, selector=wait_for_selector, error=str(e))
                
                # Wait for any additional loading
                await page.wait_for_timeout(1000)  # 1 second to ensure dynamic content loads
                
                # Get page content
                content = await page.content()
                logger.debug("Page content retrieved", url=url, content_length=len(content))
                
                return content
                
        except Exception as e:
            logger.error("Failed to get page content", url=url, error=str(e))
            return None
    
    async def take_screenshot(
        self, 
        url: str, 
        output_path: str,
        full_page: bool = True,
        browser_type: BrowserType = BrowserType.CHROMIUM
    ) -> bool:
        """Take a screenshot of a web page."""
        try:
            async with self.get_page(browser_type=browser_type) as page:
                response = await page.goto(url, wait_until="networkidle")
                
                if not response or response.status >= 400:
                    logger.warning("Failed to load page for screenshot", url=url)
                    return False
                
                # Wait for page to fully load
                await page.wait_for_timeout(2000)
                
                # Take screenshot
                await page.screenshot(path=output_path, full_page=full_page)
                logger.debug("Screenshot taken", url=url, output_path=output_path)
                
                return True
                
        except Exception as e:
            logger.error("Failed to take screenshot", url=url, error=str(e))
            return False
    
    async def generate_pdf(
        self, 
        url: str, 
        output_path: str,
        browser_type: BrowserType = BrowserType.CHROMIUM
    ) -> bool:
        """Generate PDF of a web page."""
        try:
            async with self.get_page(browser_type=browser_type) as page:
                response = await page.goto(url, wait_until="networkidle")
                
                if not response or response.status >= 400:
                    logger.warning("Failed to load page for PDF", url=url)
                    return False
                
                # Wait for page to fully load
                await page.wait_for_timeout(2000)
                
                # Generate PDF
                await page.pdf(path=output_path, format="A4", print_background=True)
                logger.debug("PDF generated", url=url, output_path=output_path)
                
                return True
                
        except Exception as e:
            logger.error("Failed to generate PDF", url=url, error=str(e))
            return False
    
    async def extract_dynamic_emails(
        self, 
        url: str, 
        browser_type: BrowserType = BrowserType.CHROMIUM
    ) -> List[str]:
        """Extract emails from dynamically loaded content."""
        try:
            async with self.get_page(browser_type=browser_type) as page:
                response = await page.goto(url, wait_until="networkidle")
                
                if not response or response.status >= 400:
                    logger.warning("Failed to load page for email extraction", url=url)
                    return []
                
                # Wait for dynamic content to load
                await page.wait_for_timeout(3000)
                
                # Execute JavaScript to find emails in the page
                emails = await page.evaluate("""
                    () => {
                        const emailRegex = /\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b/g;
                        const bodyText = document.body.innerText || document.body.textContent || '';
                        const htmlContent = document.documentElement.innerHTML;
                        
                        const allText = bodyText + ' ' + htmlContent;
                        const matches = allText.match(emailRegex) || [];
                        
                        // Remove duplicates and filter out common false positives
                        const uniqueEmails = [...new Set(matches)];
                        return uniqueEmails.filter(email => 
                            !email.includes('.png') && 
                            !email.includes('.jpg') && 
                            !email.includes('.gif') &&
                            !email.includes('example.com') &&
                            !email.includes('test.com')
                        );
                    }
                """)
                
                logger.debug("Dynamic emails extracted", url=url, count=len(emails))
                return emails
                
        except Exception as e:
            logger.error("Failed to extract dynamic emails", url=url, error=str(e))
            return []
    
    async def _periodic_cleanup(self) -> None:
        """Periodically clean up stale browser instances."""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                await self.pool.cleanup_stale_browsers(max_age_seconds=1800)  # 30 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Error in periodic cleanup", error=str(e))


# Global browser manager instance
_browser_manager: Optional[BrowserManager] = None


async def get_browser_manager() -> BrowserManager:
    """Get the global browser manager instance."""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
        await _browser_manager.start()
    return _browser_manager


async def cleanup_browser_manager() -> None:
    """Cleanup the global browser manager."""
    global _browser_manager
    if _browser_manager:
        await _browser_manager.stop()
        _browser_manager = None