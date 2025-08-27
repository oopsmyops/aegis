"""
File system utility functions for AEGIS.
Handles common file operations with proper error handling.
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional
from exceptions import FileSystemError


class FileUtils:
    """Utility class for file system operations."""
    
    @staticmethod
    def ensure_directory(directory_path: str) -> None:
        """Ensure directory exists, create if necessary."""
        try:
            Path(directory_path).expanduser().mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise FileSystemError(f"Failed to create directory {directory_path}", str(e))
    
    @staticmethod
    def copy_file(source: str, destination: str, create_dirs: bool = True) -> None:
        """Copy file from source to destination."""
        try:
            source_path = Path(source).expanduser()
            dest_path = Path(destination).expanduser()
            
            if not source_path.exists():
                raise FileSystemError(f"Source file does not exist: {source}")
            
            if create_dirs:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(source_path, dest_path)
        except Exception as e:
            raise FileSystemError(f"Failed to copy file from {source} to {destination}", str(e))
    
    @staticmethod
    def copy_directory(source: str, destination: str) -> None:
        """Copy entire directory tree."""
        try:
            source_path = Path(source).expanduser()
            dest_path = Path(destination).expanduser()
            
            if not source_path.exists():
                raise FileSystemError(f"Source directory does not exist: {source}")
            
            if dest_path.exists():
                shutil.rmtree(dest_path)
            
            shutil.copytree(source_path, dest_path)
        except Exception as e:
            raise FileSystemError(f"Failed to copy directory from {source} to {destination}", str(e))
    
    @staticmethod
    def remove_directory(directory_path: str, ignore_errors: bool = False) -> None:
        """Remove directory and all contents."""
        try:
            path = Path(directory_path).expanduser()
            if path.exists():
                shutil.rmtree(path, ignore_errors=ignore_errors)
        except Exception as e:
            if not ignore_errors:
                raise FileSystemError(f"Failed to remove directory {directory_path}", str(e))
    
    @staticmethod
    def list_files(directory_path: str, pattern: str = "*", recursive: bool = False) -> List[str]:
        """List files in directory matching pattern."""
        try:
            path = Path(directory_path).expanduser()
            if not path.exists():
                return []
            
            if recursive:
                files = list(path.rglob(pattern))
            else:
                files = list(path.glob(pattern))
            
            return [str(f) for f in files if f.is_file()]
        except Exception as e:
            raise FileSystemError(f"Failed to list files in {directory_path}", str(e))
    
    @staticmethod
    def read_file(file_path: str) -> str:
        """Read file content as string."""
        try:
            path = Path(file_path).expanduser()
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileSystemError(f"File not found: {file_path}")
        except Exception as e:
            raise FileSystemError(f"Failed to read file {file_path}", str(e))
    
    @staticmethod
    def write_file(file_path: str, content: str, create_dirs: bool = True) -> None:
        """Write content to file."""
        try:
            path = Path(file_path).expanduser()
            
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            raise FileSystemError(f"Failed to write file {file_path}", str(e))
    
    @staticmethod
    def file_exists(file_path: str) -> bool:
        """Check if file exists."""
        return Path(file_path).expanduser().exists()
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """Get file size in bytes."""
        try:
            path = Path(file_path).expanduser()
            return path.stat().st_size
        except Exception as e:
            raise FileSystemError(f"Failed to get size of file {file_path}", str(e))