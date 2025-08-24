"""Main scraper manager that orchestrates the web scraping operations."""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from scraper.core.config import Config
from scraper.core.logger import get_logger
from scraper.data.loader import DataLoader
from scraper.data.saver import DataSaver
from scraper.services.web_client import WebClient
from scraper.services.domain_processor import DomainProcessor
from scraper.services.email_extractor import EmailExtractor


class ScraperManager:
    """Main manager class that orchestrates the entire scraping process."""
    
    def __init__(self, config: Config):
        """Initialize the scraper manager with configuration."""
        self.config = config
        self.logger = get_logger("scraper_manager")
        
        # Initialize components
        self.data_loader = DataLoader()
        self.data_saver = DataSaver() 
        self.web_client = WebClient(config)
        self.domain_processor = DomainProcessor(config)
        self.email_extractor = EmailExtractor(config)
        
        self.logger.info("ScraperManager initialized", 
                        max_concurrent_domains=config.concurrency.max_concurrent_domains)
    
    async def run(self) -> None:
        """Run the main scraping process."""
        try:
            self.logger.info("Starting scraping process", input_file=self.config.input_file)
            
            # Load input data
            companies_data = await self._load_input_data()
            self.logger.info("Loaded companies data", count=len(companies_data))
            
            # Process companies to extract domains
            domains_data = await self._process_domains(companies_data)
            self.logger.info("Processed domains", count=len(domains_data))
            
            # Scrape emails from domains
            results = await self._scrape_emails(domains_data)
            self.logger.info("Scraped emails", results_count=len(results))
            
            # Save results
            await self._save_results(results)
            self.logger.info("Scraping process completed successfully")
            
        except Exception as e:
            self.logger.error("Scraping process failed", error=str(e), exc_info=True)
            raise
        finally:
            await self.web_client.close()
    
    async def _load_input_data(self) -> pd.DataFrame:
        """Load company data from input file."""
        input_path = Path(self.config.input_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {self.config.input_file}")
        
        data = await self.data_loader.load_file(str(input_path))
        
        if data.empty:
            raise ValueError("Input file is empty or contains no valid data")
        
        return data
    
    async def _process_domains(self, companies_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Process company names to extract potential domains."""
        domains_list = []
        
        for _, row in companies_data.iterrows():
            company_info = row.to_dict()
            domains = await self.domain_processor.extract_domains(company_info)
            
            for domain in domains:
                domains_list.append({
                    'original_company': company_info,
                    'domain': domain,
                    'status': 'pending'
                })
        
        return domains_list
    
    async def _scrape_emails(self, domains_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scrape emails from the list of domains."""
        semaphore = asyncio.Semaphore(self.config.concurrency.max_concurrent_domains)
        results = []
        
        async def scrape_domain(domain_info: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    domain = domain_info['domain']
                    self.logger.debug("Scraping domain", domain=domain)
                    
                    # Fetch web pages
                    pages = await self.web_client.fetch_domain_pages(domain)
                    
                    # Extract emails from pages
                    emails = []
                    for page_content in pages:
                        page_emails = await self.email_extractor.extract_emails(
                            page_content['content'], 
                            domain
                        )
                        emails.extend(page_emails)
                    
                    # Remove duplicates
                    unique_emails = list(set(emails))
                    
                    result = {
                        **domain_info,
                        'emails': unique_emails,
                        'email_count': len(unique_emails),
                        'status': 'completed',
                        'pages_scraped': len(pages)
                    }
                    
                    self.logger.info("Domain scraped successfully", 
                                   domain=domain, 
                                   emails_found=len(unique_emails))
                    
                    return result
                    
                except Exception as e:
                    self.logger.error("Failed to scrape domain", 
                                    domain=domain_info.get('domain', 'unknown'),
                                    error=str(e))
                    return {
                        **domain_info,
                        'emails': [],
                        'email_count': 0,
                        'status': 'failed',
                        'error': str(e),
                        'pages_scraped': 0
                    }
        
        # Process domains concurrently
        tasks = [scrape_domain(domain_info) for domain_info in domains_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return valid results
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error("Task failed with exception", error=str(result))
            else:
                valid_results.append(result)
        
        return valid_results
    
    async def _save_results(self, results: List[Dict[str, Any]]) -> None:
        """Save scraping results to output file."""
        if not results:
            self.logger.warning("No results to save")
            return
        
        # Convert results to DataFrame
        df_results = pd.DataFrame(results)
        
        # Flatten nested data for better output
        flattened_results = []
        for result in results:
            base_info = {
                'company_name': result['original_company'].get('name', ''),
                'domain': result['domain'],
                'status': result['status'],
                'email_count': result['email_count'],
                'pages_scraped': result.get('pages_scraped', 0)
            }
            
            if result['emails']:
                for email in result['emails']:
                    flattened_results.append({
                        **base_info,
                        'email': email
                    })
            else:
                flattened_results.append({
                    **base_info,
                    'email': '',
                    'error': result.get('error', '')
                })
        
        df_flattened = pd.DataFrame(flattened_results)
        
        # Determine output file
        if self.config.output_file:
            output_path = Path(self.config.output_file)
        else:
            input_path = Path(self.config.input_file)
            output_path = input_path.parent / f"{input_path.stem}_results.{self.config.output_format}"
        
        # Save using DataSaver
        await asyncio.to_thread(
            self.data_saver.save_to_file,
            df_flattened,
            str(output_path),
            self.config.output_format
        )
        
        self.logger.info("Results saved", 
                        output_file=str(output_path),
                        total_results=len(flattened_results),
                        successful_domains=len([r for r in results if r['status'] == 'completed']))