"""Main CLI entry point for the async scraper."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click

from scraper.core.config import Config, load_config
from scraper.core.logger import get_logger, setup_logging


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), help="Configuration file path")
@click.option("--debug", "-d", is_flag=True, help="Enable debug mode")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], debug: bool, verbose: bool) -> None:
    """Async Scraper - High-performance, async-first web scraping framework."""
    # Load configuration
    config_obj = load_config(config)
    
    # Override with CLI options
    if debug:
        config_obj.debug = True
        config_obj.logging.level = "DEBUG"
    if verbose:
        config_obj.verbose = True
    
    # Setup logging with updated config
    setup_logging(config_obj.logging.model_dump())
    
    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj["config"] = config_obj
    
    logger = get_logger("cli")
    logger.info("Async Scraper CLI initialized", version="0.1.0")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--format", "-f", "output_format", 
              type=click.Choice(["csv", "xlsx", "json"]), 
              default="csv", help="Output format")
@click.option("--max-domains", type=int, help="Maximum number of domains to process")
@click.option("--max-depth", type=int, help="Maximum crawl depth")
@click.pass_context
def scrape(ctx: click.Context, 
           input_file: str, 
           output: Optional[str], 
           output_format: str,
           max_domains: Optional[int],
           max_depth: Optional[int]) -> None:
    """Scrape emails from companies/domains in input file."""
    config: Config = ctx.obj["config"]
    logger = get_logger("cli.scrape")
    
    # Update config with CLI options
    config.input_file = input_file
    config.output_file = output
    config.output_format = output_format
    
    if max_domains:
        config.concurrency.max_concurrent_domains = max_domains
    if max_depth:
        config.scraping.max_crawl_depth = max_depth
    
    logger.info("Starting scrape operation", 
                input_file=input_file, 
                output_file=output,
                output_format=output_format)
    
    try:
        # Import and run the scraper manager
        from scraper.services.scraper_manager import ScraperManager
        
        async def run_scrape():
            manager = ScraperManager(config)
            await manager.run()
        
        asyncio.run(run_scrape())
        logger.info("Scrape operation completed successfully")
        
    except Exception as e:
        logger.error("Scrape operation failed", error=str(e), exc_info=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def test_config(ctx: click.Context) -> None:
    """Test and validate configuration."""
    config: Config = ctx.obj["config"]
    logger = get_logger("cli.test_config")
    
    logger.info("Testing configuration...")
    
    try:
        # Test configuration validation
        config_dict = config.model_dump()
        logger.info("Configuration validation passed", 
                   cache_l1_enabled=config.cache.l1_enabled,
                   max_concurrent_domains=config.concurrency.max_concurrent_domains,
                   user_agents_count=len(config.scraping.user_agents))
        
        # Test logging
        logger.debug("Debug message test")
        logger.info("Info message test")
        logger.warning("Warning message test")
        
        click.echo("✓ Configuration test completed successfully")
        
    except Exception as e:
        logger.error("Configuration test failed", error=str(e))
        click.echo(f"✗ Configuration test failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--output", "-o", type=click.Path(), default="config.json", help="Output configuration file")
@click.pass_context
def export_config(ctx: click.Context, output: str) -> None:
    """Export current configuration to file."""
    config: Config = ctx.obj["config"]
    logger = get_logger("cli.export_config")
    
    try:
        config.save_to_file(output)
        logger.info("Configuration exported", output_file=output)
        click.echo(f"✓ Configuration exported to {output}")
        
    except Exception as e:
        logger.error("Failed to export configuration", error=str(e))
        click.echo(f"✗ Failed to export configuration: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Show version information."""
    from scraper import __version__
    click.echo(f"Async Scraper v{__version__}")


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()