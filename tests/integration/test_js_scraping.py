"""
Integration tests for JavaScript scraping functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from scraper.services.js_scraper import (
    JavaScriptScraper,
    EnhancedEmailExtractor,
    ScrapingResult
)
from scraper.services.capture import CaptureService, CaptureResult
from scraper.core.config import Config, BrowserConfig


class TestJavaScriptScraperIntegration:
    """Integration tests for JavaScript scraper."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = Config()
        config.browser = BrowserConfig(
            enabled=True,
            screenshot_enabled=True,
            screenshot_format="png",
            pdf_enabled=True
        )
        config.scraping.crawl_delay = 0.1  # Reduce delay for tests
        return config
    
    @pytest.fixture
    def js_scraper(self, mock_config):
        """Create JavaScript scraper for testing."""
        with patch('scraper.services.js_scraper.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            return JavaScriptScraper()
    
    @pytest.mark.asyncio
    async def test_scrape_url_success(self, js_scraper):
        """Test successful URL scraping with JavaScript."""
        test_url = "https://example.com"
        test_content = "<html><body>Contact us at test@example.com</body></html>"
        test_emails = ["test@example.com"]
        dynamic_emails = ["dynamic@example.com"]
        
        # Mock browser manager
        mock_browser_manager = AsyncMock()
        mock_browser_manager.get_page_content.return_value = test_content
        mock_browser_manager.extract_dynamic_emails.return_value = dynamic_emails
        mock_browser_manager.take_screenshot.return_value = True
        
        # Mock email extractor
        mock_email_extractor = AsyncMock()
        mock_email_extractor.extract_from_text.return_value = test_emails
        
        with patch.object(js_scraper, '_get_browser_manager') as mock_get_bm:
            mock_get_bm.return_value = mock_browser_manager
            js_scraper.email_extractor = mock_email_extractor
            
            result = await js_scraper.scrape_url(
                url=test_url,
                extract_links=False,
                take_screenshot=True
            )
            
            assert result.success is True
            assert result.url == test_url
            assert "test@example.com" in result.emails
            assert "dynamic@example.com" in result.emails
            assert result.content == test_content
            assert result.processing_time > 0
    
    @pytest.mark.asyncio
    async def test_scrape_url_failure(self, js_scraper):
        """Test URL scraping failure."""
        test_url = "https://nonexistent.example.com"
        
        # Mock browser manager to return None (failure)
        mock_browser_manager = AsyncMock()
        mock_browser_manager.get_page_content.return_value = None
        
        with patch.object(js_scraper, '_get_browser_manager') as mock_get_bm:
            mock_get_bm.return_value = mock_browser_manager
            
            result = await js_scraper.scrape_url(url=test_url)
            
            assert result.success is False
            assert result.url == test_url
            assert result.emails == []
            assert result.error == "Failed to load page content"
    
    @pytest.mark.asyncio
    async def test_scrape_domain_with_links(self, js_scraper):
        """Test domain scraping with link extraction."""
        base_domain = "example.com"
        base_url = f"https://{base_domain}"
        
        # Mock first page with links
        page1_content = '''
        <html>
            <body>
                <a href="/about">About</a>
                <a href="https://example.com/contact">Contact</a>
                <p>Email: info@example.com</p>
            </body>
        </html>
        '''
        
        page2_content = '''
        <html>
            <body>
                <p>Support: support@example.com</p>
            </body>
        </html>
        '''
        
        # Setup mocks
        mock_browser_manager = AsyncMock()
        mock_email_extractor = AsyncMock()
        
        # Mock responses for different URLs
        async def mock_get_page_content(url, **kwargs):
            if url == base_url:
                return page1_content
            elif "about" in url or "contact" in url:
                return page2_content
            return None
        
        async def mock_extract_emails(text):
            if "info@example.com" in text:
                return ["info@example.com"]
            elif "support@example.com" in text:
                return ["support@example.com"]
            return []
        
        mock_browser_manager.get_page_content.side_effect = mock_get_page_content
        mock_browser_manager.extract_dynamic_emails.return_value = []
        mock_browser_manager.take_screenshot.return_value = True
        mock_email_extractor.extract_from_text.side_effect = mock_extract_emails
        
        with patch.object(js_scraper, '_get_browser_manager') as mock_get_bm:
            mock_get_bm.return_value = mock_browser_manager
            js_scraper.email_extractor = mock_email_extractor
            
            results = await js_scraper.scrape_domain(
                domain=base_domain,
                max_pages=3,
                max_depth=2
            )
            
            assert len(results) > 0
            assert any(r.success for r in results)
            
            # Check that we found emails from different pages
            all_emails = []
            for result in results:
                all_emails.extend(result.emails)
            
            assert len(set(all_emails)) > 0  # At least some unique emails
    
    @pytest.mark.asyncio
    async def test_scrape_company_with_js(self, js_scraper):
        """Test company scraping with JavaScript."""
        company_name = "Test Company"
        expected_domain = "testcompany.com"
        
        # Mock domain finding
        async def mock_find_company_domain(company):
            return expected_domain
        
        # Mock domain scraping
        async def mock_scrape_domain(domain, **kwargs):
            return [
                ScrapingResult(
                    url=f"https://{domain}",
                    success=True,
                    emails=["contact@testcompany.com", "info@testcompany.com"],
                    processing_time=1.0
                )
            ]
        
        with patch.object(js_scraper, '_find_company_domain') as mock_find:
            mock_find.side_effect = mock_find_company_domain
            
            with patch.object(js_scraper, 'scrape_domain') as mock_scrape:
                mock_scrape.side_effect = mock_scrape_domain
                
                result = await js_scraper.scrape_company_with_js(company_name)
                
                assert result.success is True
                assert result.url == expected_domain
                assert len(result.emails) == 2
                assert "contact@testcompany.com" in result.emails
                assert "info@testcompany.com" in result.emails


class TestEnhancedEmailExtractor:
    """Test enhanced email extractor with JavaScript support."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = Config()
        config.browser = BrowserConfig(enabled=True)
        return config
    
    @pytest.fixture
    def enhanced_extractor(self, mock_config):
        """Create enhanced email extractor for testing."""
        with patch('scraper.services.js_scraper.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            return EnhancedEmailExtractor()
    
    @pytest.mark.asyncio
    async def test_extract_emails_with_js_success(self, enhanced_extractor):
        """Test email extraction with JavaScript success."""
        test_url = "https://example.com"
        js_emails = ["js@example.com", "dynamic@example.com"]
        
        # Mock JavaScript scraper
        mock_js_result = ScrapingResult(
            url=test_url,
            success=True,
            emails=js_emails
        )
        
        enhanced_extractor.js_scraper = AsyncMock()
        enhanced_extractor.js_scraper.scrape_url.return_value = mock_js_result
        
        emails = await enhanced_extractor.extract_emails_with_js(test_url)
        
        assert emails == js_emails
        enhanced_extractor.js_scraper.scrape_url.assert_called_once_with(test_url)
    
    @pytest.mark.asyncio
    async def test_extract_emails_with_js_fallback(self, enhanced_extractor):
        """Test fallback to traditional extraction."""
        test_url = "https://example.com"
        traditional_emails = ["traditional@example.com"]
        
        # Mock JavaScript scraper failure
        mock_js_result = ScrapingResult(
            url=test_url,
            success=False,
            emails=[]
        )
        
        enhanced_extractor.js_scraper = AsyncMock()
        enhanced_extractor.js_scraper.scrape_url.return_value = mock_js_result
        
        enhanced_extractor.traditional_extractor = AsyncMock()
        enhanced_extractor.traditional_extractor.extract_from_url.return_value = traditional_emails
        
        emails = await enhanced_extractor.extract_emails_with_js(
            test_url, 
            fallback_to_traditional=True
        )
        
        assert emails == traditional_emails
        enhanced_extractor.traditional_extractor.extract_from_url.assert_called_once_with(test_url)
    
    @pytest.mark.asyncio
    async def test_extract_emails_browser_disabled(self, enhanced_extractor):
        """Test behavior when browser is disabled."""
        test_url = "https://example.com"
        traditional_emails = ["fallback@example.com"]
        
        # Disable browser in config
        enhanced_extractor.config.browser.enabled = False
        
        enhanced_extractor.traditional_extractor = AsyncMock()
        enhanced_extractor.traditional_extractor.extract_from_url.return_value = traditional_emails
        
        emails = await enhanced_extractor.extract_emails_with_js(test_url)
        
        assert emails == traditional_emails


class TestCaptureServiceIntegration:
    """Integration tests for capture service."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = Config()
        config.browser = BrowserConfig(
            screenshot_enabled=True,
            screenshot_format="png",
            screenshot_quality=80,
            pdf_enabled=True,
            pdf_format="A4"
        )
        return config
    
    @pytest.fixture
    def capture_service(self, mock_config, tmp_path):
        """Create capture service for testing."""
        with patch('scraper.services.capture.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config
            return CaptureService(output_dir=str(tmp_path / "captures"))
    
    @pytest.mark.asyncio
    async def test_take_screenshot_success(self, capture_service):
        """Test successful screenshot capture."""
        test_url = "https://example.com"
        
        # Mock browser manager
        mock_browser_manager = AsyncMock()
        mock_page = AsyncMock()
        mock_page.goto.return_value = AsyncMock(status=200)
        mock_page.screenshot = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.__aenter__ = AsyncMock(return_value=mock_page)
        mock_page.__aexit__ = AsyncMock(return_value=None)
        
        mock_browser_manager.get_page.return_value = mock_page
        
        with patch.object(capture_service, '_get_browser_manager') as mock_get_bm:
            mock_get_bm.return_value = mock_browser_manager
            
            with patch('os.path.getsize') as mock_getsize:
                mock_getsize.return_value = 1024
                
                result = await capture_service.take_screenshot(test_url)
                
                assert result.success is True
                assert result.file_path is not None
                assert result.file_size == 1024
                assert result.processing_time > 0
    
    @pytest.mark.asyncio
    async def test_generate_pdf_success(self, capture_service):
        """Test successful PDF generation."""
        test_url = "https://example.com"
        
        # Mock browser manager
        mock_browser_manager = AsyncMock()
        mock_page = AsyncMock()
        mock_page.goto.return_value = AsyncMock(status=200)
        mock_page.pdf = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.__aenter__ = AsyncMock(return_value=mock_page)
        mock_page.__aexit__ = AsyncMock(return_value=None)
        
        mock_browser_manager.get_page.return_value = mock_page
        
        with patch.object(capture_service, '_get_browser_manager') as mock_get_bm:
            mock_get_bm.return_value = mock_browser_manager
            
            with patch('os.path.getsize') as mock_getsize:
                mock_getsize.return_value = 2048
                
                result = await capture_service.generate_pdf(test_url)
                
                assert result.success is True
                assert result.file_path is not None
                assert result.file_size == 2048
                assert result.processing_time > 0
    
    @pytest.mark.asyncio
    async def test_capture_multiple_urls(self, capture_service):
        """Test capturing multiple URLs."""
        test_urls = ["https://example1.com", "https://example2.com"]
        
        # Mock successful capture for all URLs
        async def mock_take_screenshot(url, **kwargs):
            return CaptureResult(
                success=True,
                file_path=f"screenshot_{url.split('/')[-1]}.png",
                file_size=1024,
                processing_time=1.0
            )
        
        with patch.object(capture_service, 'take_screenshot') as mock_capture:
            mock_capture.side_effect = mock_take_screenshot
            
            results = await capture_service.capture_multiple_urls(
                urls=test_urls,
                capture_type="screenshot",
                concurrent_limit=2
            )
            
            assert len(results) == 2
            assert all(r.success for r in results)
            assert mock_capture.call_count == 2
    
    def test_get_capture_stats(self, capture_service):
        """Test capture statistics."""
        stats = capture_service.get_capture_stats()
        
        assert "screenshots" in stats
        assert "pdfs" in stats
        assert "output_directory" in stats
        assert stats["screenshots"]["count"] >= 0
        assert stats["pdfs"]["count"] >= 0