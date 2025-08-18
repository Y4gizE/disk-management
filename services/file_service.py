import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
import logging

class FileService:
    def __init__(self, base_path: str):
        """
        Initialize the FileService with the base shared directory path.
        
        Args:
            base_path (str): The base directory path for shared files
        """
        self.base_path = Path(base_path).resolve()
        self.logger = logging.getLogger(__name__)
        
        # Create base directory if it doesn't exist
        self.ensure_directory_exists(self.base_path)
    
    def ensure_directory_exists(self, path: Path) -> None:
        """Ensure the specified directory exists, create if it doesn't."""
        try:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created directory: {path}")
        except Exception as e:
            self.logger.error(f"Error ensuring directory exists {path}: {e}")
            raise
    
    def get_directory_listing(self, path: str = '') -> Tuple[List[dict], List[dict]]:
        """
        Get directory listing with files and subdirectories.
        
        Args:
            path (str): Relative path from base directory
            
        Returns:
            Tuple containing (directories, files) where each is a list of dicts
            with file/folder information
        """
        try:
            full_path = (self.base_path / path).resolve()
            
            # Security check: Ensure the path is within base directory
            if not str(full_path).startswith(str(self.base_path)):
                raise ValueError("Access denied: Path is outside the base directory")
                
            if not full_path.exists() or not full_path.is_dir():
                raise FileNotFoundError(f"Directory not found: {path}")
            
            dirs = []
            files = []
            
            for item in full_path.iterdir():
                try:
                    stat = item.stat()
                    item_info = {
                        'name': item.name,
                        'path': str(item.relative_to(self.base_path)),
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'is_dir': item.is_dir()
                    }
                    
                    if item.is_dir():
                        dirs.append(item_info)
                    else:
                        files.append(item_info)
                        
                except (PermissionError, OSError) as e:
                    self.logger.warning(f"Could not access {item}: {e}")
                    continue
                    
            # Sort directories and files
            dirs.sort(key=lambda x: x['name'].lower())
            files.sort(key=lambda x: x['name'].lower())
            
            return dirs, files
            
        except Exception as e:
            self.logger.error(f"Error getting directory listing for {path}: {e}")
            raise
    
    def get_file_info(self, relative_path: str) -> dict:
        """
        Get information about a file or directory.
        
        Args:
            relative_path (str): Path relative to base directory
            
        Returns:
            dict: File/directory information
        """
        try:
            full_path = (self.base_path / relative_path).resolve()
            
            # Security check
            if not str(full_path).startswith(str(self.base_path)):
                raise ValueError("Access denied: Path is outside the base directory")
                
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {relative_path}")
                
            stat = full_path.stat()
            
            return {
                'name': full_path.name,
                'path': str(relative_path),
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'is_dir': full_path.is_dir(),
                'parent': str(full_path.parent.relative_to(self.base_path))
            }
            
        except Exception as e:
            self.logger.error(f"Error getting file info for {relative_path}: {e}")
            raise
    
    def create_directory(self, path: str, name: str) -> None:
        """
        Create a new directory.
        
        Args:
            path (str): Parent directory path relative to base
            name (str): Name of new directory to create
        """
        try:
            parent_path = (self.base_path / path).resolve()
            new_dir = parent_path / name
            
            # Security check
            if not str(parent_path).startswith(str(self.base_path)):
                raise ValueError("Access denied: Path is outside the base directory")
                
            if not parent_path.exists() or not parent_path.is_dir():
                raise FileNotFoundError(f"Parent directory not found: {path}")
                
            new_dir.mkdir(exist_ok=False)
            self.logger.info(f"Created directory: {new_dir}")
            
        except FileExistsError:
            raise FileExistsError(f"Directory already exists: {name}")
        except Exception as e:
            self.logger.error(f"Error creating directory {name} in {path}: {e}")
            raise
    
    def delete_path(self, path: str) -> None:
        """
        Delete a file or directory.
        
        Args:
            path (str): Path relative to base directory
        """
        try:
            full_path = (self.base_path / path).resolve()
            
            # Security check
            if not str(full_path).startswith(str(self.base_path)):
                raise ValueError("Access denied: Path is outside the base directory")
                
            if not full_path.exists():
                raise FileNotFoundError(f"Path not found: {path}")
                
            if full_path.is_dir():
                shutil.rmtree(full_path)
                self.logger.info(f"Deleted directory: {full_path}")
            else:
                full_path.unlink()
                self.logger.info(f"Deleted file: {full_path}")
                
        except Exception as e:
            self.logger.error(f"Error deleting {path}: {e}")
            raise
    
    def get_file_path(self, relative_path: str) -> Path:
        """
        Get the full filesystem path for a relative path.
        
        Args:
            relative_path (str): Path relative to base directory
            
        Returns:
            Path: Full filesystem path
        """
        full_path = (self.base_path / relative_path).resolve()
        
        # Security check
        if not str(full_path).startswith(str(self.base_path)):
            raise ValueError("Access denied: Path is outside the base directory")
            
        if not full_path.exists():
            raise FileNotFoundError(f"Path not found: {relative_path}")
            
        return full_path
