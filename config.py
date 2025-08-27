"""
Configuration management system for AEGIS CLI tool.
Handles YAML configuration loading, validation, and default values.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from interfaces import ConfigurationInterface
from exceptions import ConfigurationError


class ConfigurationManager(ConfigurationInterface):
    """Manages AEGIS configuration with YAML support."""
    
    DEFAULT_CONFIG_NAME = "aegis-config.yaml"
    DEFAULT_CONFIG_PATHS = [
        "./aegis-config.yaml",
        "~/.aegis/config.yaml",
        "/etc/aegis/config.yaml"
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager."""
        self.config_path = config_path
        self._config: Optional[Dict[str, Any]] = None
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from file."""
        if config_path:
            self.config_path = config_path
        
        # Try to find config file
        config_file = self._find_config_file()
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ConfigurationError(f"Invalid YAML in config file {config_file}: {e}")
            except Exception as e:
                raise ConfigurationError(f"Error reading config file {config_file}: {e}")
        else:
            config = {}
        
        # Merge with defaults
        default_config = self.get_default_config()
        merged_config = self._deep_merge(default_config, config)
        
        # Validate configuration
        if not self.validate_config(merged_config):
            raise ConfigurationError("Configuration validation failed")
        
        self._config = merged_config
        return merged_config
    
    def save_config(self, config: Dict[str, Any], config_path: Optional[str] = None) -> None:
        """Save configuration to file."""
        if config_path:
            self.config_path = config_path
        
        if not self.config_path:
            self.config_path = self.DEFAULT_CONFIG_PATHS[0]
        
        # Ensure directory exists
        config_dir = os.path.dirname(os.path.expanduser(self.config_path))
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        
        try:
            with open(os.path.expanduser(self.config_path), 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2)
        except Exception as e:
            raise ConfigurationError(f"Error saving config file {self.config_path}: {e}")
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "cluster": {
                "kubeconfig_path": "~/.kube/config",
                "context": None,
                "timeout": 60
            },
            "questionnaire": {
                "total_questions": 20
            },
            "catalog": {
                "repositories": [
                    {
                        "url": "https://github.com/kyverno/policies",
                        "branch": "main"
                    },
                    {
                        "url": "https://github.com/nirmata/kyverno-policies", 
                        "branch": "main"
                    }
                ],
                "local_storage": "./policy-catalog",
                "index_file": "./policy-index.json"
            },
            "ai": {
                "provider": "aws-bedrock",
                "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                "region": "us-east-1",
                "max_tokens": 4000,
                "temperature": 0.1,
                "policy_count": {
                    "total_target": 20
                },
                "catalog_sampling": {
                    "max_policies_per_category": 10,
                    "total_policies_for_ai": 50
                }
            },
            "output": {
                "directory": "./recommended-policies",
                "dynamic_categories": True,
                "include_tests": False,
                "validate_policies": False
            },
            "logging": {
                "level": "INFO",
                "file": "./aegis.log"
            }
        }
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration structure and values."""
        required_sections = ["cluster", "questionnaire", "catalog", "ai", "output", "logging"]
        
        for section in required_sections:
            if section not in config:
                return False
        
        # Validate cluster section
        cluster_config = config.get("cluster", {})
        if not isinstance(cluster_config.get("timeout"), int) or cluster_config["timeout"] <= 0:
            return False
        
        # Validate questionnaire section
        questionnaire_config = config.get("questionnaire", {})
        if not isinstance(questionnaire_config.get("total_questions"), int) or questionnaire_config["total_questions"] <= 0:
            return False
        
        # Validate AI section
        ai_config = config.get("ai", {})
        if not ai_config.get("model") or not ai_config.get("region"):
            return False
        
        policy_count = ai_config.get("policy_count", {})
        if not isinstance(policy_count.get("total_target"), int) or policy_count["total_target"] <= 0:
            return False
        
        return True
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration, loading if necessary."""
        if self._config is None:
            self.load_config()
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key."""
        config = self.get_config()
        keys = key.split('.')
        
        current = config
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in standard locations."""
        if self.config_path:
            return os.path.expanduser(self.config_path)
        
        for path in self.DEFAULT_CONFIG_PATHS:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                return expanded_path
        
        return None
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result