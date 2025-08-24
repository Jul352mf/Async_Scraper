"""Domain processor for converting company names to potential domains."""

import re
from typing import List, Dict, Any, Set
from urllib.parse import urlparse

from scraper.core.config import Config
from scraper.core.logger import get_logger


class DomainProcessor:
    """Processor for extracting and generating potential domains from company information."""
    
    def __init__(self, config: Config):
        """Initialize the domain processor."""
        self.config = config
        self.logger = get_logger("domain_processor")
        
        # Common company suffixes to remove/replace
        self.company_suffixes = {
            'inc', 'incorporated', 'corp', 'corporation', 'company', 'co', 'ltd', 'limited',
            'llc', 'llp', 'lp', 'pc', 'pllc', 'group', 'holdings', 'enterprises',
            'industries', 'services', 'solutions', 'systems', 'technologies', 'tech',
            'international', 'intl', 'global', 'worldwide', 'associates', 'partners'
        }
        
        # Common domain extensions
        self.common_tlds = ['.com', '.org', '.net', '.co', '.io', '.biz', '.info']
        
        # Words to remove that don't help with domain generation
        self.stopwords = {
            'the', 'and', 'or', 'of', 'in', 'at', 'to', 'for', 'with', 'by', 'from',
            'a', 'an', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            '&', '+', '-', '_'
        }
    
    async def extract_domains(self, company_info: Dict[str, Any]) -> List[str]:
        """Extract potential domains from company information."""
        domains = set()
        
        # Get company name and other relevant fields
        company_name = self._get_company_name(company_info)
        
        if not company_name:
            self.logger.warning("No company name found", company_info=company_info)
            return []
        
        self.logger.debug("Processing company", name=company_name)
        
        # Check if there's already a domain/website field
        existing_domain = self._extract_existing_domain(company_info)
        if existing_domain:
            domains.add(existing_domain)
        
        # Generate domains from company name
        generated_domains = self._generate_domains_from_name(company_name)
        domains.update(generated_domains)
        
        # Convert to list and validate
        domain_list = list(domains)
        validated_domains = []
        
        for domain in domain_list:
            if self._is_valid_domain(domain):
                validated_domains.append(domain)
            else:
                self.logger.debug("Invalid domain filtered out", domain=domain)
        
        self.logger.debug("Generated domains", 
                         company=company_name,
                         domains=validated_domains,
                         count=len(validated_domains))
        
        return validated_domains
    
    def _get_company_name(self, company_info: Dict[str, Any]) -> str:
        """Extract company name from various possible field names."""
        # Common field names for company names
        name_fields = [
            'name', 'company_name', 'company', 'business_name', 'organization',
            'title', 'entity', 'firm', 'Name', 'Company', 'Company Name'
        ]
        
        for field in name_fields:
            if field in company_info and company_info[field]:
                return str(company_info[field]).strip()
        
        # If no name field found, try to get the first non-empty value
        for key, value in company_info.items():
            if value and isinstance(value, str) and value.strip():
                return value.strip()
        
        return ""
    
    def _extract_existing_domain(self, company_info: Dict[str, Any]) -> str:
        """Extract existing domain/website from company info."""
        # Common field names for domains/websites
        domain_fields = [
            'domain', 'website', 'url', 'web', 'homepage', 'site',
            'Domain', 'Website', 'URL', 'Web', 'Homepage', 'Site'
        ]
        
        for field in domain_fields:
            if field in company_info and company_info[field]:
                domain = str(company_info[field]).strip()
                # Clean up the domain
                domain = self._clean_domain(domain)
                if domain:
                    return domain
        
        return ""
    
    def _clean_domain(self, domain: str) -> str:
        """Clean and validate a domain string."""
        domain = domain.strip().lower()
        
        # Remove common prefixes
        if domain.startswith(('http://', 'https://')):
            parsed = urlparse(domain)
            domain = parsed.netloc
        elif domain.startswith('www.'):
            domain = domain[4:]
        
        # Remove trailing slashes and paths
        if '/' in domain:
            domain = domain.split('/')[0]
        
        return domain
    
    def _generate_domains_from_name(self, company_name: str) -> Set[str]:
        """Generate potential domains from company name."""
        domains = set()
        
        # Clean and normalize company name
        cleaned_name = self._clean_company_name(company_name)
        
        if not cleaned_name:
            return domains
        
        # Generate various domain combinations
        name_parts = cleaned_name.split()
        
        # Full name variations
        full_name = ''.join(name_parts)
        full_name_dash = '-'.join(name_parts)
        
        for tld in self.common_tlds:
            # Full company name
            domains.add(f"{full_name}{tld}")
            domains.add(f"{full_name_dash}{tld}")
            
            # First word only
            if name_parts:
                first_word = name_parts[0]
                domains.add(f"{first_word}{tld}")
            
            # First and last word
            if len(name_parts) >= 2:
                first_last = f"{name_parts[0]}{name_parts[-1]}"
                first_last_dash = f"{name_parts[0]}-{name_parts[-1]}"
                domains.add(f"{first_last}{tld}")
                domains.add(f"{first_last_dash}{tld}")
            
            # Acronym (first letter of each word)
            if len(name_parts) >= 2:
                acronym = ''.join(word[0] for word in name_parts if word)
                domains.add(f"{acronym}{tld}")
        
        return domains
    
    def _clean_company_name(self, name: str) -> str:
        """Clean company name for domain generation."""
        # Convert to lowercase
        name = name.lower().strip()
        
        # Remove special characters and normalize
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'\s+', ' ', name)  # Multiple spaces to single space
        
        # Split into words
        words = name.split()
        
        # Remove company suffixes
        cleaned_words = []
        for word in words:
            word = word.strip('.,!?;:')  # Remove punctuation
            
            # Skip empty words or stopwords
            if not word or word in self.stopwords:
                continue
            
            # Remove common company suffixes
            if word not in self.company_suffixes:
                cleaned_words.append(word)
        
        # If we removed all words, use the original (minus stopwords)
        if not cleaned_words:
            cleaned_words = [word for word in words if word and word not in self.stopwords]
        
        return ' '.join(cleaned_words)
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Validate if a domain string is potentially valid."""
        if not domain:
            return False
        
        # Basic domain validation
        domain_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\.[a-zA-Z]{2,}$'
        
        # Allow domains without TLD for internal processing
        if '.' not in domain:
            return False
        
        # Check basic pattern
        if not re.match(domain_pattern, domain):
            return False
        
        # Check length
        if len(domain) > 255 or len(domain) < 4:
            return False
        
        # Check for consecutive dots or dashes
        if '..' in domain or '--' in domain:
            return False
        
        # Check if starts/ends with dash
        if domain.startswith('-') or domain.endswith('-'):
            return False
        
        return True