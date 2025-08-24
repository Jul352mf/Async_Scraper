"""Basic tests for configuration and logging."""

import pytest
from pathlib import Path
import tempfile
import json

from scraper.core.config import Config, get_config, set_config, load_config
from scraper.core.logger import get_logger


class TestConfig:
    """Test configuration management."""
    
    def test_default_config(self):
        """Test default configuration creation."""
        config = Config()
        assert config.cache.l1_enabled is True
        assert config.cache.l1_max_size == 1000
        assert config.concurrency.max_concurrent_domains == 10
        assert len(config.scraping.user_agents) == 3
        
    def test_config_validation(self):
        """Test configuration validation."""
        config = Config(output_format="csv")
        assert config.output_format == "csv"
        
        with pytest.raises(ValueError):
            Config(output_format="invalid")
            
    def test_config_to_dict(self):
        """Test configuration to dictionary conversion."""
        config = Config()
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert "cache" in config_dict
        assert "concurrency" in config_dict
        
    def test_config_save_load(self):
        """Test configuration save and load."""
        config = Config(debug=True, verbose=True)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name
            
        try:
            config.save_to_file(config_path)
            
            # Verify file exists and contains valid JSON
            assert Path(config_path).exists()
            with open(config_path, 'r') as f:
                data = json.load(f)
                assert data["debug"] is True
                assert data["verbose"] is True
                
            # Load config from file
            loaded_config = Config.load_from_file(config_path)
            assert loaded_config.debug is True
            assert loaded_config.verbose is True
            
        finally:
            Path(config_path).unlink(missing_ok=True)
            
    def test_global_config(self):
        """Test global configuration management."""
        # Create and set a config
        config = Config(debug=True)
        set_config(config)
        
        # Retrieve global config
        global_config = get_config()
        assert global_config.debug is True
        assert global_config is config


class TestLogger:
    """Test logging functionality."""
    
    def test_get_logger(self):
        """Test logger creation."""
        logger = get_logger("test")
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")
        
    def test_logger_with_context(self):
        """Test logger with initial context."""
        logger = get_logger("test", session_id="123", user="testuser")
        # This should not raise an error
        logger.info("Test message with context")
        
    def test_multiple_loggers(self):
        """Test creating multiple loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        
        assert logger1 is not logger2
        # But getting the same logger name should return the same instance
        logger1_again = get_logger("module1")
        assert logger1 is not logger1_again  # structlog creates new bound instances


if __name__ == "__main__":
    pytest.main([__file__])