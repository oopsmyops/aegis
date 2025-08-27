"""
YAML utility functions for AEGIS.
Handles YAML file operations with proper error handling.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from exceptions import FileSystemError


class YamlUtils:
    """Utility class for YAML operations."""
    
    @staticmethod
    def load_yaml(file_path: str) -> Dict[str, Any]:
        """Load YAML file and return parsed content."""
        try:
            path = Path(file_path).expanduser()
            with open(path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
                return content if content is not None else {}
        except FileNotFoundError:
            raise FileSystemError(f"YAML file not found: {file_path}")
        except yaml.YAMLError as e:
            raise FileSystemError(f"Invalid YAML in file {file_path}", str(e))
        except Exception as e:
            raise FileSystemError(f"Error reading YAML file {file_path}", str(e))
    
    @staticmethod
    def load_yaml_safe(file_path: str) -> Dict[str, Any]:
        """Load YAML file safely, handling multi-document files by returning first valid document."""
        try:
            path = Path(file_path).expanduser()
            with open(path, 'r', encoding='utf-8') as f:
                # Try to load all documents and return the first valid one
                documents = list(yaml.safe_load_all(f))
                for doc in documents:
                    if doc is not None and isinstance(doc, dict):
                        return doc
                return {}
        except FileNotFoundError:
            raise FileSystemError(f"YAML file not found: {file_path}")
        except yaml.YAMLError as e:
            # If multi-document parsing fails, try single document
            try:
                path = Path(file_path).expanduser()
                with open(path, 'r', encoding='utf-8') as f:
                    content = yaml.safe_load(f)
                    return content if content is not None else {}
            except:
                raise FileSystemError(f"Invalid YAML in file {file_path}", str(e))
        except Exception as e:
            raise FileSystemError(f"Error reading YAML file {file_path}", str(e))
    
    @staticmethod
    def save_yaml(data: Dict[str, Any], file_path: str, create_dirs: bool = True) -> None:
        """Save data to YAML file."""
        try:
            path = Path(file_path).expanduser()
            
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, indent=2, sort_keys=False)
        except Exception as e:
            raise FileSystemError(f"Error writing YAML file {file_path}", str(e))
    
    @staticmethod
    def append_to_yaml(new_data: Dict[str, Any], file_path: str, merge_key: Optional[str] = None) -> None:
        """Append data to existing YAML file."""
        try:
            # Load existing data
            existing_data = YamlUtils.load_yaml(file_path) if Path(file_path).exists() else {}
            
            if merge_key:
                # Merge under specific key
                if merge_key not in existing_data:
                    existing_data[merge_key] = {}
                existing_data[merge_key].update(new_data)
            else:
                # Merge at root level
                existing_data.update(new_data)
            
            # Save merged data
            YamlUtils.save_yaml(existing_data, file_path)
        except Exception as e:
            raise FileSystemError(f"Error appending to YAML file {file_path}", str(e))
    
    @staticmethod
    def load_yaml_safe_from_string(yaml_content: str) -> Dict[str, Any]:
        """Load YAML content from string safely."""
        try:
            if not yaml_content or not yaml_content.strip():
                return {}
            
            # Try to load all documents and return the first valid one
            documents = list(yaml.safe_load_all(yaml_content))
            for doc in documents:
                if doc is not None and isinstance(doc, dict):
                    return doc
            return {}
        except yaml.YAMLError as e:
            # If multi-document parsing fails, try single document
            try:
                content = yaml.safe_load(yaml_content)
                return content if content is not None else {}
            except:
                raise FileSystemError(f"Invalid YAML content", str(e))
        except Exception as e:
            raise FileSystemError(f"Error parsing YAML content", str(e))
    
    @staticmethod
    def dump_yaml_safe(data: Dict[str, Any]) -> str:
        """Convert data to YAML string safely."""
        try:
            return yaml.dump(data, default_flow_style=False, indent=2, sort_keys=False)
        except Exception as e:
            raise FileSystemError(f"Error converting data to YAML string", str(e))
    
    @staticmethod
    def validate_yaml_structure(data: Dict[str, Any], required_keys: list) -> bool:
        """Validate that YAML data contains required keys."""
        for key in required_keys:
            if '.' in key:
                # Handle nested keys
                keys = key.split('.')
                current = data
                for k in keys:
                    if not isinstance(current, dict) or k not in current:
                        return False
                    current = current[k]
            else:
                if key not in data:
                    return False
        return True