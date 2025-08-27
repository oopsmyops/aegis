"""
Tests for configuration management.
"""

import pytest
import tempfile
import os
from pathlib import Path
from aegis.config import ConfigurationManager
from aegis.exceptions import ConfigurationError


class TestConfigurationManager:
    """Test configuration management functionality."""
    
    def test_default_config_structure(self):
        """Test that default configuration has required structure."""
        config_manager = ConfigurationManager()
        default_config = config_manager.get_default_config()
        
        required_sections = ["cluster", "questionnaire", "catalog", "ai", "output", "logging"]
        for section in required_sections:
            assert section in default_config
    
    def test_config_validation(self):
        """Test configuration validation."""
        config_manager = ConfigurationManager()
        
        # Valid config should pass
        valid_config = config_manager.get_default_config()
        assert config_manager.validate_config(valid_config) is True
        
        # Invalid config should fail
        invalid_config = {"cluster": {}}  # Missing required sections
        assert config_manager.validate_config(invalid_config) is False
    
    def test_config_save_and_load(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = os.path.join(temp_dir, "test-config.yaml")
            config_manager = ConfigurationManager(config_file)
            
            # Save default config
            default_config = config_manager.get_default_config()
            config_manager.save_config(default_config, config_file)
            
            # Load and verify
            loaded_config = config_manager.load_config(config_file)
            assert loaded_config == default_config
    
    def test_config_get_method(self):
        """Test configuration value retrieval with dot notation."""
        config_manager = ConfigurationManager()
        config_manager._config = config_manager.get_default_config()
        
        # Test nested key access
        timeout = config_manager.get("cluster.timeout")
        assert timeout == 60
        
        # Test default value
        non_existent = config_manager.get("non.existent.key", "default")
        assert non_existent == "default"