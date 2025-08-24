"""Tests for the scraping services."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from scraper.core.config import Config
from scraper.services.domain_processor import DomainProcessor
from scraper.services.email_extractor import EmailExtractor


class TestDomainProcessor:
    """Test domain processor functionality."""
    
    @pytest.fixture
    def config(self):
        return Config()
    
    @pytest.fixture 
    def processor(self, config):
        return DomainProcessor(config)
    
    @pytest.mark.asyncio
    async def test_extract_existing_domain(self, processor):
        """Test extracting existing domain from company info."""
        company_info = {
            'name': 'Test Company',
            'website': 'https://test.com'
        }
        
        domains = await processor.extract_domains(company_info)
        
        assert len(domains) == 1
        assert domains[0] == 'test.com'
    
    @pytest.mark.asyncio 
    async def test_generate_domains_from_name(self, processor):
        """Test domain generation from company name."""
        company_info = {
            'name': 'Test Company Inc'
        }
        
        domains = await processor.extract_domains(company_info)
        
        assert len(domains) > 0
        # Should generate domains like test.com, testcompany.com etc
        assert any('test' in domain for domain in domains)
    
    def test_clean_domain(self, processor):
        """Test domain cleaning functionality."""
        assert processor._clean_domain('https://test.com/path') == 'test.com'
        assert processor._clean_domain('www.test.com') == 'test.com'
        assert processor._clean_domain('test.com/') == 'test.com'
    
    def test_is_valid_domain(self, processor):
        """Test domain validation."""
        assert processor._is_valid_domain('test.com') == True
        assert processor._is_valid_domain('sub.test.com') == True
        assert processor._is_valid_domain('invalid') == False
        assert processor._is_valid_domain('.com') == False
        assert processor._is_valid_domain('test..com') == False


class TestEmailExtractor:
    """Test email extraction functionality."""
    
    @pytest.fixture
    def config(self):
        return Config()
    
    @pytest.fixture
    def extractor(self, config):
        return EmailExtractor(config)
    
    @pytest.mark.asyncio
    async def test_extract_emails_from_text(self, extractor):
        """Test email extraction from HTML content."""
        html_content = """
        <html>
        <body>
        <p>Contact us at info@company.com or support@company.com</p>
        <a href="mailto:contact@company.com">Email us</a>
        </body>
        </html>
        """
        
        emails = await extractor.extract_emails(html_content, 'company.com')
        
        assert len(emails) > 0
        assert any('info@company.com' == email or 'contact@company.com' == email for email in emails)
    
    def test_email_validation(self, extractor):
        """Test email format validation."""
        assert extractor._is_potentially_valid_email('test@example.com') == True
        assert extractor._is_potentially_valid_email('invalid-email') == False
        assert extractor._is_potentially_valid_email('@example.com') == False
        assert extractor._is_potentially_valid_email('test@') == False
    
    def test_filter_emails(self, extractor):
        """Test email filtering logic."""
        emails = {
            'info@company.com',      # Good
            'noreply@company.com',   # Should be filtered
            'user@gmail.com',        # Should be filtered (common provider)
            'contact@company.com'    # Good
        }
        
        filtered = extractor._filter_emails(emails, 'company.com')
        
        assert 'info@company.com' in filtered
        assert 'contact@company.com' in filtered
        assert 'noreply@company.com' not in filtered
        assert 'user@gmail.com' not in filtered