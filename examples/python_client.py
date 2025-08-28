#!/usr/bin/env python3
"""
Comprehensive Python Client for Async_Scraper API

This example demonstrates all major features including:
- Multi-tenant authentication
- Traditional and JavaScript scraping
- Proxy management
- Real-time WebSocket updates
- Error handling and retry logic
- Performance monitoring
"""

import asyncio
import aiohttp
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import websockets


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapingConfig:
    """Configuration for scraping operations."""
    timeout: int = 30
    max_crawl_depth: int = 3
    respect_robots_txt: bool = True
    use_proxies: bool = True
    proxy_strategy: str = "fastest"
    take_screenshots: bool = False
    browser_type: str = "chromium"


class AsyncScraperClient:
    """Comprehensive Python client for Async_Scraper API."""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = None
        self.headers = {"X-API-Key": api_key} if api_key else {}
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=300)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    # Health and System Status
    async def health_check(self, detailed: bool = False) -> Dict:
        """Perform health check."""
        endpoint = "/health/detailed" if detailed else "/health"
        try:
            async with self.session.get(f"{self.base_url}{endpoint}") as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Health check failed: {e}")
            raise
            
    # Traditional Scraping
    async def scrape_companies(
        self, 
        companies: List[str], 
        max_emails_per_company: int = 50,
        config: Optional[ScrapingConfig] = None
    ) -> str:
        """Create a company scraping job."""
        config = config or ScrapingConfig()
        
        payload = {
            "companies": companies,
            "max_emails_per_company": max_emails_per_company,
            "config": {
                "scraping": {
                    "timeout": config.timeout,
                    "max_crawl_depth": config.max_crawl_depth,
                    "respect_robots_txt": config.respect_robots_txt
                },
                "proxy": {
                    "enabled": config.use_proxies,
                    "rotation_strategy": config.proxy_strategy
                }
            }
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/scrape/companies",
                json=payload
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Created company scraping job: {result['job_id']}")
                return result["job_id"]
        except aiohttp.ClientError as e:
            logger.error(f"Failed to create company scraping job: {e}")
            raise
            
    async def scrape_domains(
        self, 
        domains: List[str], 
        max_depth: int = 3,
        max_emails_per_domain: int = 100,
        config: Optional[ScrapingConfig] = None
    ) -> str:
        """Create a domain scraping job."""
        config = config or ScrapingConfig()
        
        payload = {
            "domains": domains,
            "max_depth": max_depth,
            "max_emails_per_domain": max_emails_per_domain,
            "config": {
                "scraping": {
                    "timeout": config.timeout,
                    "respect_robots_txt": config.respect_robots_txt
                }
            }
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/scrape/domains",
                json=payload
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Created domain scraping job: {result['job_id']}")
                return result["job_id"]
        except aiohttp.ClientError as e:
            logger.error(f"Failed to create domain scraping job: {e}")
            raise
            
    # JavaScript Scraping
    async def scrape_companies_js(
        self, 
        companies: List[str], 
        max_emails_per_company: int = 50,
        config: Optional[ScrapingConfig] = None
    ) -> str:
        """Create a JavaScript-enabled company scraping job."""
        config = config or ScrapingConfig()
        
        payload = {
            "companies": companies,
            "max_emails_per_company": max_emails_per_company,
            "config": {
                "browser_type": config.browser_type,
                "headless": True,
                "take_screenshots": config.take_screenshots,
                "use_proxies": config.use_proxies,
                "proxy_strategy": config.proxy_strategy,
                "wait_timeout": 10000,
                "viewport": {
                    "width": 1920,
                    "height": 1080
                }
            }
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/enhanced/scrape/companies/js",
                json=payload
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Created JavaScript scraping job: {result['job_id']}")
                return result["job_id"]
        except aiohttp.ClientError as e:
            logger.error(f"Failed to create JavaScript scraping job: {e}")
            raise
            
    # Visual Capture
    async def capture_screenshots(
        self, 
        urls: List[str], 
        full_page: bool = True,
        format: str = "png"
    ) -> str:
        """Capture screenshots of web pages."""
        payload = {
            "urls": urls,
            "config": {
                "full_page": full_page,
                "format": format,
                "quality": 90,
                "viewport": {
                    "width": 1920,
                    "height": 1080
                },
                "delay_ms": 2000
            }
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/enhanced/capture/screenshot",
                json=payload
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Created screenshot job: {result['job_id']}")
                return result["job_id"]
        except aiohttp.ClientError as e:
            logger.error(f"Failed to create screenshot job: {e}")
            raise
            
    async def generate_pdfs(
        self, 
        urls: List[str], 
        format: str = "A4"
    ) -> str:
        """Generate PDF documents from web pages."""
        payload = {
            "urls": urls,
            "config": {
                "format": format,
                "landscape": False,
                "margin": {
                    "top": "1cm",
                    "right": "1cm", 
                    "bottom": "1cm",
                    "left": "1cm"
                },
                "print_background": True,
                "delay_ms": 3000
            }
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/enhanced/capture/pdf",
                json=payload
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Created PDF job: {result['job_id']}")
                return result["job_id"]
        except aiohttp.ClientError as e:
            logger.error(f"Failed to create PDF job: {e}")
            raise
            
    # Job Management
    async def list_jobs(
        self, 
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> Dict:
        """List jobs with filtering."""
        params = {"limit": limit, "skip": skip}
        if status:
            params["status"] = status
        if job_type:
            params["job_type"] = job_type
            
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/jobs",
                params=params
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Failed to list jobs: {e}")
            raise
            
    async def get_job_status(self, job_id: str) -> Dict:
        """Get job status and details."""
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/jobs/{job_id}"
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Failed to get job status: {e}")
            raise
            
    async def get_job_results(self, job_id: str) -> Dict:
        """Get job results."""
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/jobs/{job_id}/results"
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Failed to get job results: {e}")
            raise
            
    async def cancel_job(self, job_id: str) -> Dict:
        """Cancel a running job."""
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/jobs/{job_id}/cancel"
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Cancelled job: {job_id}")
                return result
        except aiohttp.ClientError as e:
            logger.error(f"Failed to cancel job: {e}")
            raise
            
    async def delete_job(self, job_id: str) -> Dict:
        """Delete a completed job."""
        try:
            async with self.session.delete(
                f"{self.base_url}/api/v1/jobs/{job_id}"
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Deleted job: {job_id}")
                return result
        except aiohttp.ClientError as e:
            logger.error(f"Failed to delete job: {e}")
            raise
            
    # Proxy Management
    async def list_proxies(self, status: Optional[str] = None) -> Dict:
        """List all proxies."""
        params = {}
        if status:
            params["status"] = status
            
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/proxy/proxies",
                params=params
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Failed to list proxies: {e}")
            raise
            
    async def create_proxy(
        self, 
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        country_code: Optional[str] = None
    ) -> str:
        """Create a new proxy configuration."""
        payload = {"url": url}
        if username:
            payload["username"] = username
        if password:
            payload["password"] = password
        if country_code:
            payload["country_code"] = country_code
            
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/proxy/proxies",
                json=payload
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Created proxy: {result['id']}")
                return result["id"]
        except aiohttp.ClientError as e:
            logger.error(f"Failed to create proxy: {e}")
            raise
            
    async def get_proxy_stats(self) -> Dict:
        """Get proxy system statistics."""
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/proxy/stats"
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Failed to get proxy stats: {e}")
            raise
            
    # Utility Methods
    async def wait_for_completion(
        self, 
        job_id: str, 
        poll_interval: int = 5,
        timeout: int = 3600
    ) -> Dict:
        """Wait for job to complete and return results."""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
                
            status_data = await self.get_job_status(job_id)
            status = status_data["status"]
            
            logger.info(f"Job {job_id} status: {status}")
            
            if status == "completed":
                logger.info(f"Job {job_id} completed successfully")
                return await self.get_job_results(job_id)
            elif status in ["failed", "cancelled"]:
                raise Exception(f"Job {job_id} {status}: {status_data.get('error', 'Unknown error')}")
                
            await asyncio.sleep(poll_interval)


class WebSocketClient:
    """WebSocket client for real-time job updates."""
    
    def __init__(self, base_url: str, api_key: str):
        self.ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{self.ws_url}/api/v1/ws?api_key={api_key}"
        self.websocket = None
        
    async def connect(self):
        """Connect to WebSocket."""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            logger.info("Connected to WebSocket")
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            raise
            
    async def disconnect(self):
        """Disconnect from WebSocket."""
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from WebSocket")
            
    async def subscribe_to_job(self, job_id: str):
        """Subscribe to job updates."""
        if not self.websocket:
            raise Exception("WebSocket not connected")
            
        message = {
            "action": "subscribe",
            "job_id": job_id
        }
        await self.websocket.send(json.dumps(message))
        logger.info(f"Subscribed to job updates: {job_id}")
        
    async def listen(self, message_handler=None):
        """Listen for WebSocket messages."""
        if not self.websocket:
            raise Exception("WebSocket not connected")
            
        try:
            async for message in self.websocket:
                data = json.loads(message)
                
                if message_handler:
                    await message_handler(data)
                else:
                    await self._default_message_handler(data)
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            
    async def _default_message_handler(self, data: Dict):
        """Default message handler."""
        message_type = data.get("type")
        
        if message_type == "job_update":
            job_id = data.get("job_id")
            progress = data.get("job", {}).get("progress", {})
            percent = progress.get("percent", 0)
            current_item = progress.get("current_item", "")
            logger.info(f"Job {job_id}: {percent:.1f}% complete, processing {current_item}")
            
        elif message_type == "job_completed":
            job_id = data.get("job_id")
            status = data.get("job", {}).get("status")
            logger.info(f"Job {job_id} completed with status: {status}")
            
        elif message_type == "error":
            logger.error(f"WebSocket error: {data.get('message')}")
            
        else:
            logger.debug(f"Received message: {data}")


# Example Usage Functions
async def example_traditional_scraping():
    """Example: Traditional HTTP scraping."""
    async with AsyncScraperClient(api_key="your-tenant-api-key") as client:
        # Health check
        health = await client.health_check(detailed=True)
        logger.info(f"System status: {health['status']}")
        
        # Create scraping job
        companies = ["Google", "Microsoft", "OpenAI"]
        job_id = await client.scrape_companies(
            companies=companies,
            max_emails_per_company=10,
            config=ScrapingConfig(use_proxies=True, proxy_strategy="fastest")
        )
        
        # Wait for completion
        results = await client.wait_for_completion(job_id)
        
        # Display results
        emails_found = results["results"]["total_emails_found"]
        logger.info(f"Found {emails_found} emails from {len(companies)} companies")
        
        for company, emails in results["results"]["emails_by_company"].items():
            logger.info(f"{company}: {len(emails)} emails")


async def example_javascript_scraping():
    """Example: JavaScript-enabled scraping with screenshots."""
    async with AsyncScraperClient(api_key="your-tenant-api-key") as client:
        # JavaScript scraping with screenshots
        companies = ["OpenAI", "Stripe", "Vercel"]
        job_id = await client.scrape_companies_js(
            companies=companies,
            max_emails_per_company=15,
            config=ScrapingConfig(
                take_screenshots=True,
                browser_type="chromium",
                use_proxies=True
            )
        )
        
        # Monitor progress via WebSocket
        ws_client = WebSocketClient("ws://localhost:8000", "your-tenant-api-key")
        await ws_client.connect()
        await ws_client.subscribe_to_job(job_id)
        
        # Listen to updates while waiting
        async def custom_handler(data):
            if data.get("type") == "job_completed":
                await ws_client.disconnect()
                
        # Start listening task
        listen_task = asyncio.create_task(ws_client.listen(custom_handler))
        
        # Wait for completion
        try:
            results = await client.wait_for_completion(job_id, timeout=600)
            
            # Check for screenshots
            screenshots = results["results"].get("screenshots", {})
            if screenshots:
                logger.info("Screenshots captured:")
                for company, url in screenshots.items():
                    logger.info(f"  {company}: {url}")
                    
        except Exception as e:
            logger.error(f"Job failed: {e}")
        finally:
            listen_task.cancel()


async def example_visual_capture():
    """Example: Screenshot and PDF generation."""
    async with AsyncScraperClient(api_key="your-tenant-api-key") as client:
        urls = ["https://example.com", "https://docs.python.org"]
        
        # Capture screenshots
        screenshot_job = await client.capture_screenshots(
            urls=urls,
            full_page=True,
            format="png"
        )
        
        # Generate PDFs
        pdf_job = await client.generate_pdfs(
            urls=urls,
            format="A4"
        )
        
        # Wait for both jobs
        screenshot_results = await client.wait_for_completion(screenshot_job)
        pdf_results = await client.wait_for_completion(pdf_job)
        
        logger.info("Visual capture completed:")
        logger.info(f"Screenshots: {len(screenshot_results['results'])} files")
        logger.info(f"PDFs: {len(pdf_results['results'])} files")


async def example_proxy_management():
    """Example: Comprehensive proxy management."""
    async with AsyncScraperClient(api_key="your-tenant-api-key") as client:
        # List existing proxies
        proxies = await client.list_proxies()
        logger.info(f"Current proxies: {len(proxies['proxies'])}")
        
        # Add new proxy
        proxy_id = await client.create_proxy(
            url="http://proxy.example.com:8080",
            username="user",
            password="pass",
            country_code="US"
        )
        
        # Get proxy statistics
        stats = await client.get_proxy_stats()
        logger.info(f"Proxy stats: {stats['proxy_stats']['healthy_proxies']}/{stats['proxy_stats']['total_proxies']} healthy")


async def example_batch_processing():
    """Example: Batch processing with job management."""
    async with AsyncScraperClient(api_key="your-tenant-api-key") as client:
        # Create multiple jobs
        company_batches = [
            ["Google", "Microsoft", "Apple"],
            ["Amazon", "Meta", "Netflix"],
            ["OpenAI", "Stripe", "Vercel"]
        ]
        
        job_ids = []
        for batch in company_batches:
            job_id = await client.scrape_companies_js(
                companies=batch,
                max_emails_per_company=5,
                config=ScrapingConfig(take_screenshots=True)
            )
            job_ids.append(job_id)
            
        logger.info(f"Created {len(job_ids)} batch jobs")
        
        # Monitor all jobs
        while job_ids:
            completed_jobs = []
            
            for job_id in job_ids[:]:  # Copy list to avoid modification during iteration
                status_data = await client.get_job_status(job_id)
                status = status_data["status"]
                progress = status_data.get("progress", {}).get("percent", 0)
                
                logger.info(f"Job {job_id}: {status} ({progress:.1f}%)")
                
                if status in ["completed", "failed", "cancelled"]:
                    completed_jobs.append(job_id)
                    job_ids.remove(job_id)
                    
            if job_ids:  # Still have pending jobs
                await asyncio.sleep(10)
                
        logger.info("All batch jobs completed")
        
        # Collect results
        total_emails = 0
        for job_id in completed_jobs:
            try:
                results = await client.get_job_results(job_id)
                emails_found = results["results"]["total_emails_found"]
                total_emails += emails_found
                logger.info(f"Job {job_id}: {emails_found} emails found")
            except Exception as e:
                logger.error(f"Failed to get results for job {job_id}: {e}")
                
        logger.info(f"Total emails found across all batches: {total_emails}")


if __name__ == "__main__":
    # Set up your API key
    import os
    api_key = os.getenv("ASYNC_SCRAPER_API_KEY", "your-tenant-api-key")
    
    # Run examples
    asyncio.run(example_traditional_scraping())
    asyncio.run(example_javascript_scraping())
    asyncio.run(example_visual_capture())
    asyncio.run(example_proxy_management())
    asyncio.run(example_batch_processing())