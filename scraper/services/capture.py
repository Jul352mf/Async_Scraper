"""
Capture Service for Screenshots and PDF Generation

This module provides screenshot and PDF generation capabilities using browser automation.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
import re

import structlog

from scraper.core.config import get_config
from scraper.core.logger import get_logger
from scraper.services.browser_manager import get_browser_manager, BrowserType

logger = get_logger(__name__)


@dataclass
class CaptureResult:
    """Result from a capture operation."""
    success: bool
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class CaptureService:
    """Service for capturing screenshots and generating PDFs."""
    
    def __init__(self, output_dir: str = "captures"):
        self.config = get_config()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.output_dir / "screenshots").mkdir(exist_ok=True)
        (self.output_dir / "pdfs").mkdir(exist_ok=True)
        
        self._browser_manager = None
    
    async def _get_browser_manager(self):
        """Get browser manager instance."""
        if self._browser_manager is None:
            self._browser_manager = await get_browser_manager()
        return self._browser_manager
    
    def _sanitize_filename(self, url: str, prefix: str = "") -> str:
        """Create a safe filename from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc or "unknown"
        path = parsed.path or ""
        
        # Clean domain and path
        domain = re.sub(r'[^\w\-.]', '_', domain)
        path = re.sub(r'[^\w\-/]', '_', path).replace('/', '_')
        
        # Create timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Combine parts
        filename_parts = [prefix, domain]
        if path and path != '_':
            filename_parts.append(path[:20])  # Limit path length
        filename_parts.append(timestamp)
        
        return '_'.join(filter(None, filename_parts))
    
    async def take_screenshot(
        self,
        url: str,
        output_path: Optional[str] = None,
        full_page: bool = True,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        wait_for_selector: Optional[str] = None,
        wait_timeout: int = 5000,
        browser_type: BrowserType = BrowserType.CHROMIUM
    ) -> CaptureResult:
        """Take a screenshot of a webpage."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            if not self.config.browser.screenshot_enabled:
                return CaptureResult(
                    success=False,
                    error="Screenshot capture is disabled in configuration"
                )
            
            browser_manager = await self._get_browser_manager()
            
            # Generate output path if not provided
            if not output_path:
                filename = f"{self._sanitize_filename(url, 'screenshot')}.{self.config.browser.screenshot_format}"
                output_path = str(self.output_dir / "screenshots" / filename)
            
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Custom context options for screenshot
            context_options = {
                "viewport": {
                    "width": viewport_width,
                    "height": viewport_height
                }
            }
            
            async with browser_manager.get_page(browser_type=browser_type, context_options=context_options) as page:
                # Navigate to the page
                response = await page.goto(url, wait_until="networkidle")
                
                if not response or response.status >= 400:
                    return CaptureResult(
                        success=False,
                        error=f"Failed to load page: {response.status if response else 'No response'}"
                    )
                
                # Wait for specific selector if provided
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=wait_timeout)
                    except Exception as e:
                        logger.warning("Selector wait failed", url=url, selector=wait_for_selector, error=str(e))
                
                # Wait for page to fully load
                await page.wait_for_timeout(2000)
                
                # Take screenshot
                screenshot_options = {
                    "path": output_path,
                    "full_page": full_page,
                    "type": self.config.browser.screenshot_format
                }
                
                if self.config.browser.screenshot_format == "jpeg":
                    screenshot_options["quality"] = self.config.browser.screenshot_quality
                
                await page.screenshot(**screenshot_options)
                
                # Get file info
                file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                processing_time = asyncio.get_event_loop().time() - start_time
                
                # Get page metadata
                page_metadata = await self._get_page_metadata(page)
                
                logger.info("Screenshot captured successfully",
                           url=url,
                           output_path=output_path,
                           file_size=file_size,
                           processing_time=processing_time)
                
                return CaptureResult(
                    success=True,
                    file_path=output_path,
                    file_size=file_size,
                    processing_time=processing_time,
                    metadata=page_metadata
                )
        
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.error("Screenshot capture failed", url=url, error=str(e))
            
            return CaptureResult(
                success=False,
                error=str(e),
                processing_time=processing_time
            )
    
    async def generate_pdf(
        self,
        url: str,
        output_path: Optional[str] = None,
        format: str = "A4",
        landscape: bool = False,
        print_background: bool = True,
        margin: Optional[Dict[str, str]] = None,
        wait_for_selector: Optional[str] = None,
        wait_timeout: int = 5000,
        browser_type: BrowserType = BrowserType.CHROMIUM
    ) -> CaptureResult:
        """Generate PDF of a webpage."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            if not self.config.browser.pdf_enabled:
                return CaptureResult(
                    success=False,
                    error="PDF generation is disabled in configuration"
                )
            
            browser_manager = await self._get_browser_manager()
            
            # Generate output path if not provided
            if not output_path:
                filename = f"{self._sanitize_filename(url, 'pdf')}.pdf"
                output_path = str(self.output_dir / "pdfs" / filename)
            
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Default margin if not provided
            if margin is None:
                margin = {"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"}
            
            async with browser_manager.get_page(browser_type=browser_type) as page:
                # Navigate to the page
                response = await page.goto(url, wait_until="networkidle")
                
                if not response or response.status >= 400:
                    return CaptureResult(
                        success=False,
                        error=f"Failed to load page: {response.status if response else 'No response'}"
                    )
                
                # Wait for specific selector if provided
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=wait_timeout)
                    except Exception as e:
                        logger.warning("Selector wait failed", url=url, selector=wait_for_selector, error=str(e))
                
                # Wait for page to fully load
                await page.wait_for_timeout(2000)
                
                # Generate PDF
                pdf_options = {
                    "path": output_path,
                    "format": format,
                    "landscape": landscape,
                    "print_background": print_background,
                    "margin": margin
                }
                
                await page.pdf(**pdf_options)
                
                # Get file info
                file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                processing_time = asyncio.get_event_loop().time() - start_time
                
                # Get page metadata
                page_metadata = await self._get_page_metadata(page)
                
                logger.info("PDF generated successfully",
                           url=url,
                           output_path=output_path,
                           file_size=file_size,
                           processing_time=processing_time)
                
                return CaptureResult(
                    success=True,
                    file_path=output_path,
                    file_size=file_size,
                    processing_time=processing_time,
                    metadata=page_metadata
                )
        
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.error("PDF generation failed", url=url, error=str(e))
            
            return CaptureResult(
                success=False,
                error=str(e),
                processing_time=processing_time
            )
    
    async def capture_multiple_urls(
        self,
        urls: List[str],
        capture_type: str = "screenshot",  # "screenshot" or "pdf"
        concurrent_limit: int = 3,
        **capture_options
    ) -> List[CaptureResult]:
        """Capture multiple URLs concurrently."""
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def capture_single(url: str) -> CaptureResult:
            async with semaphore:
                if capture_type == "screenshot":
                    return await self.take_screenshot(url, **capture_options)
                elif capture_type == "pdf":
                    return await self.generate_pdf(url, **capture_options)
                else:
                    return CaptureResult(
                        success=False,
                        error=f"Unknown capture type: {capture_type}"
                    )
        
        # Create tasks for all URLs
        tasks = [capture_single(url) for url in urls]
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(CaptureResult(
                    success=False,
                    error=f"Exception during capture: {str(result)}"
                ))
            else:
                processed_results.append(result)
        
        successful_captures = sum(1 for r in processed_results if r.success)
        logger.info("Batch capture completed",
                   total_urls=len(urls),
                   successful=successful_captures,
                   capture_type=capture_type)
        
        return processed_results
    
    async def _get_page_metadata(self, page) -> Dict[str, Any]:
        """Extract metadata from page."""
        try:
            metadata = await page.evaluate("""
                () => {
                    const title = document.title;
                    const url = window.location.href;
                    const viewport = {
                        width: window.innerWidth,
                        height: window.innerHeight
                    };
                    
                    // Get meta tags
                    const metaTags = {};
                    const metas = document.querySelectorAll('meta');
                    for (let meta of metas) {
                        const name = meta.name || meta.property || meta.httpEquiv;
                        const content = meta.content;
                        if (name && content) {
                            metaTags[name] = content;
                        }
                    }
                    
                    return {
                        title,
                        url,
                        viewport,
                        metaTags,
                        timestamp: new Date().toISOString()
                    };
                }
            """)
            
            return metadata
        except Exception as e:
            logger.warning("Failed to extract page metadata", error=str(e))
            return {"error": str(e)}
    
    def get_capture_stats(self) -> Dict[str, Any]:
        """Get statistics about captured files."""
        try:
            screenshots_dir = self.output_dir / "screenshots"
            pdfs_dir = self.output_dir / "pdfs"
            
            screenshot_files = list(screenshots_dir.glob("*")) if screenshots_dir.exists() else []
            pdf_files = list(pdfs_dir.glob("*")) if pdfs_dir.exists() else []
            
            screenshot_total_size = sum(f.stat().st_size for f in screenshot_files if f.is_file())
            pdf_total_size = sum(f.stat().st_size for f in pdf_files if f.is_file())
            
            return {
                "screenshots": {
                    "count": len(screenshot_files),
                    "total_size_bytes": screenshot_total_size,
                    "total_size_mb": round(screenshot_total_size / (1024 * 1024), 2)
                },
                "pdfs": {
                    "count": len(pdf_files),
                    "total_size_bytes": pdf_total_size,
                    "total_size_mb": round(pdf_total_size / (1024 * 1024), 2)
                },
                "output_directory": str(self.output_dir)
            }
        except Exception as e:
            logger.error("Failed to get capture stats", error=str(e))
            return {"error": str(e)}
    
    def cleanup_old_captures(self, max_age_days: int = 7) -> Dict[str, int]:
        """Clean up old capture files."""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        cleaned_files = {"screenshots": 0, "pdfs": 0}
        
        try:
            for subdir in ["screenshots", "pdfs"]:
                dir_path = self.output_dir / subdir
                if dir_path.exists():
                    for file_path in dir_path.glob("*"):
                        if file_path.is_file():
                            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                            if file_mtime < cutoff_date:
                                file_path.unlink()
                                cleaned_files[subdir] += 1
            
            logger.info("Cleanup completed", 
                       screenshots_cleaned=cleaned_files["screenshots"],
                       pdfs_cleaned=cleaned_files["pdfs"],
                       max_age_days=max_age_days)
            
        except Exception as e:
            logger.error("Cleanup failed", error=str(e))
        
        return cleaned_files


# Global capture service instance
_capture_service: Optional[CaptureService] = None


def get_capture_service(output_dir: str = "captures") -> CaptureService:
    """Get the global capture service instance."""
    global _capture_service
    if _capture_service is None:
        _capture_service = CaptureService(output_dir)
    return _capture_service