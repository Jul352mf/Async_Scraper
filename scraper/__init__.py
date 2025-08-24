"""Async Scraper - High-performance, async-first web scraping framework."""

__version__ = "0.1.0"
__author__ = "Async Scraper Team"
__email__ = "team@async-scraper.dev"

from scraper.core.config import Config
from scraper.core.logger import get_logger

__all__ = ["Config", "get_logger"]