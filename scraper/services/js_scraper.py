"""
JavaScript Content Scraper

This module provides JavaScript-based scraping capabilities using Playwright
for dynamic content that requires browser rendering.
"""

import asyncio
from typing import List, Optional, Dict, Any, Set
from urllib.parse import urljoin, urlparse
import re
from dataclasses import dataclass

import structlog
from bs4 import BeautifulSoup

from scraper.core.config import get_config
from scraper.core.logger import get_logger
from scraper.services.browser_manager import get_browser_manager, BrowserType
from scraper.services.email_extractor import EmailExtractor

logger = get_logger(__name__)


@dataclass
class ScrapingResult:
    """Result from JavaScript scraping operation."""
    url: str
    success: bool
    emails: List[str]
    content: Optional[str] = None
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    links_found: List[str] = None
    processing_time: float = 0.0


class JavaScriptScraper:
    """Scraper for JavaScript-heavy websites using browser automation."""
    
    def __init__(self):
        self.config = get_config()
        self.email_extractor = EmailExtractor()
        self._browser_manager = None
        
    async def _get_browser_manager(self):
        """Get browser manager instance."""
        if self._browser_manager is None:
            self._browser_manager = await get_browser_manager()
        return self._browser_manager
    
    async def scrape_url(
        self, 
        url: str, 
        wait_for_selector: Optional[str] = None,
        wait_for_timeout: Optional[int] = None,
        extract_links: bool = False,
        take_screenshot: bool = False,
        screenshot_path: Optional[str] = None
    ) -> ScrapingResult:
        """Scrape a single URL with JavaScript rendering."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            browser_manager = await self._get_browser_manager()
            
            # Get page content with JavaScript rendering
            content = await browser_manager.get_page_content(
                url=url,
                wait_for_selector=wait_for_selector,
                wait_for_timeout=wait_for_timeout
            )
            
            if not content:
                return ScrapingResult(
                    url=url,
                    success=False,
                    emails=[],
                    error="Failed to load page content"
                )
            
            # Extract emails from rendered content
            emails = await self.email_extractor.extract_from_text(content)
            
            # Additionally try dynamic email extraction
            dynamic_emails = await browser_manager.extract_dynamic_emails(url)
            
            # Combine and deduplicate emails
            all_emails = list(set(emails + dynamic_emails))
            
            # Extract links if requested
            links = []
            if extract_links:
                links = await self._extract_links(content, url)
            
            # Take screenshot if requested
            screenshot_taken = False
            if take_screenshot and self.config.browser.screenshot_enabled:
                if not screenshot_path:
                    safe_domain = re.sub(r'[^\w\-.]', '_', urlparse(url).netloc)
                    screenshot_path = f"screenshots/{safe_domain}_{int(start_time)}.{self.config.browser.screenshot_format}"
                
                screenshot_taken = await browser_manager.take_screenshot(
                    url=url,
                    output_path=screenshot_path,
                    full_page=True
                )
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.debug("JavaScript scraping completed",
                        url=url,
                        emails_found=len(all_emails),
                        links_found=len(links),
                        screenshot_taken=screenshot_taken,
                        processing_time=processing_time)
            
            return ScrapingResult(
                url=url,
                success=True,
                emails=all_emails,
                content=content,
                screenshot_path=screenshot_path if screenshot_taken else None,
                links_found=links,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.error("JavaScript scraping failed", url=url, error=str(e))
            
            return ScrapingResult(
                url=url,
                success=False,
                emails=[],
                error=str(e),
                processing_time=processing_time
            )
    
    async def scrape_domain(
        self, 
        domain: str, 
        max_pages: int = 10,
        max_depth: int = 3,
        include_external_links: bool = False
    ) -> List[ScrapingResult]:
        """Scrape multiple pages from a domain with JavaScript support."""
        base_url = f"https://{domain}" if not domain.startswith(('http://', 'https://')) else domain
        
        visited_urls: Set[str] = set()
        urls_to_visit: List[tuple] = [(base_url, 0)]  # (url, depth)
        results: List[ScrapingResult] = []
        
        logger.info("Starting domain scraping with JavaScript", 
                   domain=domain, max_pages=max_pages, max_depth=max_depth)
        
        while urls_to_visit and len(results) < max_pages:
            current_url, depth = urls_to_visit.pop(0)
            
            if current_url in visited_urls or depth > max_depth:
                continue
            
            visited_urls.add(current_url)
            
            # Scrape current page
            result = await self.scrape_url(
                url=current_url,
                extract_links=(depth < max_depth),  # Only extract links if we can go deeper
                take_screenshot=(depth == 0)  # Take screenshot of homepage only
            )
            
            results.append(result)
            
            # Add found links to visit queue if we haven't reached max depth
            if result.success and result.links_found and depth < max_depth:
                for link in result.links_found:
                    if link not in visited_urls:
                        # Check if we should follow this link
                        if include_external_links or self._is_same_domain(link, domain):
                            urls_to_visit.append((link, depth + 1))
            
            # Add small delay between requests
            await asyncio.sleep(self.config.scraping.crawl_delay)
        
        total_emails = sum(len(result.emails) for result in results if result.success)
        total_time = sum(result.processing_time for result in results)
        
        logger.info("Domain scraping completed",
                   domain=domain,
                   pages_scraped=len(results),
                   successful_pages=sum(1 for r in results if r.success),
                   total_emails=total_emails,
                   total_time=total_time)
        
        return results
    
    async def scrape_company_with_js(
        self, 
        company_name: str, 
        max_emails: int = 50
    ) -> ScrapingResult:
        """Scrape a company using JavaScript-enabled browser automation."""
        # Try to find company domain first using a search approach
        company_domain = await self._find_company_domain(company_name)
        
        if not company_domain:
            return ScrapingResult(
                url=f"search:{company_name}",
                success=False,
                emails=[],
                error="Could not find company domain"
            )
        
        # Scrape the company domain
        results = await self.scrape_domain(
            domain=company_domain,
            max_pages=min(10, max_emails // 5),  # Reasonable page limit
            max_depth=2
        )
        
        # Combine all emails from all pages
        all_emails = []
        for result in results:
            if result.success:
                all_emails.extend(result.emails)
        
        # Remove duplicates and limit to max_emails
        unique_emails = list(set(all_emails))[:max_emails]
        
        # Return combined result
        return ScrapingResult(
            url=company_domain,
            success=len(unique_emails) > 0,
            emails=unique_emails,
            content=None,  # Don't store content for company results
            processing_time=sum(r.processing_time for r in results)
        )
    
    async def _extract_links(self, html_content: str, base_url: str) -> List[str]:
        """Extract links from HTML content."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            
            for tag in soup.find_all(['a', 'area'], href=True):
                href = tag['href']
                
                # Skip non-HTTP links
                if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                    continue
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    href = urljoin(base_url, href)
                elif not href.startswith(('http://', 'https://')):
                    href = urljoin(base_url, href)
                
                links.append(href)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_links = []
            for link in links:
                if link not in seen:
                    seen.add(link)
                    unique_links.append(link)
            
            return unique_links[:50]  # Limit to 50 links to prevent explosion
            
        except Exception as e:
            logger.warning("Failed to extract links", base_url=base_url, error=str(e))
            return []
    
    def _is_same_domain(self, url: str, base_domain: str) -> bool:
        """Check if URL belongs to the same domain."""
        try:
            parsed_url = urlparse(url)
            url_domain = parsed_url.netloc.lower()
            base_domain = base_domain.lower()
            
            # Remove www. prefix for comparison
            url_domain = url_domain.replace('www.', '')
            base_domain = base_domain.replace('www.', '')
            
            return url_domain == base_domain or url_domain.endswith('.' + base_domain)
        except:
            return False
    
    async def _find_company_domain(self, company_name: str) -> Optional[str]:
        """Find company domain using browser search."""
        try:
            browser_manager = await self._get_browser_manager()
            
            # Create a search query
            search_query = f"{company_name} official website"
            search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            
            # Use browser to perform search
            async with browser_manager.get_page() as page:
                try:
                    await page.goto(search_url, wait_until="networkidle")
                    await page.wait_for_timeout(2000)
                    
                    # Extract first organic search result
                    first_result = await page.evaluate("""
                        () => {
                            const result = document.querySelector('div.yuRUbf a');
                            return result ? result.href : null;
                        }
                    """)
                    
                    if first_result:
                        parsed = urlparse(first_result)
                        domain = parsed.netloc.replace('www.', '')
                        logger.debug("Company domain found", company=company_name, domain=domain)
                        return domain
                    
                except Exception as e:
                    logger.warning("Search failed", company=company_name, error=str(e))
            
            # Fallback: try constructing domain from company name
            fallback_domain = f"{company_name.lower().replace(' ', '').replace(',', '').replace('.', '')}.com"
            logger.debug("Using fallback domain", company=company_name, domain=fallback_domain)
            return fallback_domain
            
        except Exception as e:
            logger.error("Failed to find company domain", company=company_name, error=str(e))
            return None


class EnhancedEmailExtractor:
    """Enhanced email extractor with JavaScript support."""
    
    def __init__(self):
        self.js_scraper = JavaScriptScraper()
        self.traditional_extractor = EmailExtractor()
        self.config = get_config()
    
    async def extract_emails_with_js(
        self, 
        url: str,
        fallback_to_traditional: bool = True
    ) -> List[str]:
        """Extract emails using JavaScript scraping with traditional fallback."""
        
        # Try JavaScript scraping first
        if self.config.browser.enabled:
            js_result = await self.js_scraper.scrape_url(url)
            if js_result.success and js_result.emails:
                logger.debug("JavaScript email extraction successful", 
                           url=url, count=len(js_result.emails))
                return js_result.emails
        
        # Fallback to traditional scraping if enabled and JS failed
        if fallback_to_traditional:
            logger.debug("Falling back to traditional email extraction", url=url)
            return await self.traditional_extractor.extract_from_url(url)
        
        return []