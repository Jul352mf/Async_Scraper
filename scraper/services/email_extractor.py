"""Email extractor for finding email addresses in web content."""

import re
from typing import List, Set, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from scraper.core.config import Config
from scraper.core.logger import get_logger


class EmailExtractor:
    """Extractor for finding email addresses in HTML content."""
    
    def __init__(self, config: Config):
        """Initialize the email extractor."""
        self.config = config
        self.logger = get_logger("email_extractor")
        
        # Comprehensive email regex pattern
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        )
        
        # More specific pattern for high-quality emails
        self.quality_email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        )
        
        # Common email prefixes that suggest real contact emails
        self.contact_prefixes = {
            'contact', 'info', 'hello', 'support', 'sales', 'admin', 'office',
            'team', 'general', 'inquiries', 'mail', 'email', 'help',
            'business', 'hr', 'jobs', 'careers', 'press', 'media',
            'ceo', 'founder', 'owner', 'manager', 'director'
        }
        
        # Email patterns to avoid (likely not real contact emails)
        self.avoid_patterns = {
            'example', 'test', 'sample', 'dummy', 'fake', 'noreply', 'no-reply',
            'donotreply', 'do-not-reply', 'mailer-daemon', 'postmaster',
            'newsletter', 'marketing', 'promo', 'ads', 'advertising'
        }
        
        # Domains to avoid (common email providers, not business emails)
        self.avoid_domains = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com',
            'aol.com', 'icloud.com', 'me.com', 'mail.com', 'ymail.com',
            'protonmail.com', 'tutanota.com'
        }
    
    async def extract_emails(self, content: str, domain: str) -> List[str]:
        """Extract email addresses from HTML content."""
        if not content:
            return []
        
        emails = set()
        
        try:
            # Parse HTML content
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove script and style elements
            for element in soup(["script", "style", "noscript"]):
                element.decompose()
            
            # Extract emails from different sources
            text_emails = self._extract_from_text(soup.get_text())
            href_emails = self._extract_from_links(soup)
            
            emails.update(text_emails)
            emails.update(href_emails)
            
            # Filter and validate emails
            filtered_emails = self._filter_emails(emails, domain)
            
            self.logger.debug("Extracted emails", 
                            domain=domain,
                            raw_count=len(emails),
                            filtered_count=len(filtered_emails))
            
            return list(filtered_emails)
            
        except Exception as e:
            self.logger.error("Error extracting emails", 
                            domain=domain, 
                            error=str(e))
            return []
    
    def _extract_from_text(self, text: str) -> Set[str]:
        """Extract emails from plain text content."""
        emails = set()
        
        # Find all email matches
        matches = self.email_pattern.findall(text)
        
        for match in matches:
            # Clean up the email
            email = match.strip().lower()
            if self._is_potentially_valid_email(email):
                emails.add(email)
        
        return emails
    
    def _extract_from_links(self, soup: BeautifulSoup) -> Set[str]:
        """Extract emails from mailto links and other href attributes."""
        emails = set()
        
        # Find mailto links
        mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.I))
        
        for link in mailto_links:
            href = link.get('href', '')
            if href.startswith('mailto:'):
                email_part = href[7:]  # Remove 'mailto:' prefix
                
                # Handle multiple emails or additional parameters
                email_part = email_part.split('?')[0]  # Remove query parameters
                email_part = email_part.split('&')[0]  # Remove additional parameters
                
                # Handle multiple emails separated by commas or semicolons
                for email in re.split(r'[,;]', email_part):
                    email = email.strip().lower()
                    if self._is_potentially_valid_email(email):
                        emails.add(email)
        
        # Also check href attributes for plain email addresses
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            # Sometimes emails are in href without mailto:
            email_matches = self.email_pattern.findall(href)
            for email in email_matches:
                email = email.strip().lower()
                if self._is_potentially_valid_email(email):
                    emails.add(email)
        
        return emails
    
    def _is_potentially_valid_email(self, email: str) -> bool:
        """Basic validation for potentially valid emails."""
        if not email or '@' not in email:
            return False
        
        # Check length
        if len(email) > 254 or len(email) < 5:
            return False
        
        # Check for basic email structure
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            return False
        
        return True
    
    def _filter_emails(self, emails: Set[str], target_domain: str) -> Set[str]:
        """Filter emails to keep only relevant, high-quality ones."""
        filtered_emails = set()
        
        # Clean target domain
        target_domain = target_domain.lower()
        if target_domain.startswith(('http://', 'https://')):
            parsed = urlparse(target_domain)
            target_domain = parsed.netloc
        if target_domain.startswith('www.'):
            target_domain = target_domain[4:]
        
        for email in emails:
            if not email:
                continue
            
            email_lower = email.lower()
            
            # Skip if contains avoid patterns
            if any(pattern in email_lower for pattern in self.avoid_patterns):
                self.logger.debug("Skipping email with avoid pattern", email=email)
                continue
            
            # Extract domain from email
            email_domain = email_lower.split('@')[1] if '@' in email_lower else ''
            
            # Skip common email providers (unless it's specifically requested)
            if email_domain in self.avoid_domains:
                self.logger.debug("Skipping common email provider", email=email)
                continue
            
            # Prefer emails from the same domain as the website
            is_same_domain = target_domain in email_domain or email_domain in target_domain
            
            # Prefer emails with contact-related prefixes
            email_prefix = email_lower.split('@')[0] if '@' in email_lower else ''
            is_contact_email = any(prefix in email_prefix for prefix in self.contact_prefixes)
            
            # Score the email based on various factors
            score = 0
            
            if is_same_domain:
                score += 10
            
            if is_contact_email:
                score += 5
            
            # Simple format check (no numbers at start, reasonable length)
            if not email_prefix.startswith(tuple('0123456789')):
                score += 2
            
            if 5 <= len(email_prefix) <= 20:
                score += 1
            
            # Only keep emails with reasonable scores
            if score >= 3 or is_same_domain:
                filtered_emails.add(email)
                self.logger.debug("Keeping email", 
                                email=email,
                                score=score,
                                same_domain=is_same_domain,
                                is_contact=is_contact_email)
            else:
                self.logger.debug("Filtering out low-score email", 
                                email=email,
                                score=score)
        
        return filtered_emails
    
    def validate_email_format(self, email: str) -> bool:
        """Validate email format more strictly."""
        if not email:
            return False
        
        # Comprehensive email validation regex
        pattern = r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        
        return re.match(pattern, email) is not None