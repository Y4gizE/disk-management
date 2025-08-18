"""Utility helper functions for the application."""
import os
import socket
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union
from datetime import datetime
import mimetypes
import hashlib
import json
import shutil
import re

# Configure logging
logger = logging.getLogger(__name__)

# Initialize mimetypes
mimetypes.init()

def get_local_ip() -> str:
    """Get the local IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.1)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception as e:
        logger.error(f"Error getting local IP: {e}")
        return "127.0.0.1"

def get_public_ip() -> Optional[str]:
    """Get the public IP address."""
    try:
        import requests
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        response.raise_for_status()
        return response.json().get('ip')
    except Exception as e:
        logger.error(f"Error getting public IP: {e}")
        return None

def get_folder_size(path: Union[str, Path]) -> int:
    """Calculate the total size of a folder in bytes."""
    path = Path(path)
    if not path.exists() or not path.is_dir():
        return 0
    
    total_size = 0
    for item in path.rglob('*'):
        try:
            if item.is_file():
                total_size += item.stat().st_size
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not access {item}: {e}")
            continue
    return total_size

def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    if not isinstance(size_bytes, (int, float)) or size_bytes < 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    
    while size_bytes >= 1024 and unit_index < len(units) - 1:
        size_bytes /= 1024
        unit_index += 1
    
    return f"{size_bytes:.1f} {units[unit_index]}"

def get_mime_type(file_path: Union[str, Path]) -> str:
    """Get the MIME type of a file."""
    file_path = Path(file_path)
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or 'application/octet-stream'

def is_safe_path(base_path: Union[str, Path], target_path: Union[str, Path]) -> bool:
    """Check if target path is within base path."""
    try:
        base = Path(base_path).resolve()
        target = Path(target_path).resolve()
        return base in target.parents or base == target
    except Exception as e:
        logger.error(f"Error checking path safety: {e}")
        return False

def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing unsafe characters."""
    sanitized = re.sub(r'[^\w\s.-]', '', filename)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    if not sanitized:
        sanitized = f"unnamed_file_{int(datetime.now().timestamp())}"
    return sanitized

def get_relative_path(base_path: Union[str, Path], full_path: Union[str, Path]) -> str:
    """Get relative path from base path."""
    try:
        base = Path(base_path).resolve()
        full = Path(full_path).resolve()
        return str(full.relative_to(base))
    except ValueError:
        return str(full_path)

def build_directory_structure(base_path: Union[str, Path], max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
    """Build a hierarchical directory structure."""
    base_path = Path(base_path).resolve()
    result = {
        'name': base_path.name,
        'path': str(base_path),
        'is_dir': True,
        'size': 0,
        'children': []
    }
    
    if current_depth >= max_depth:
        return result
        
    try:
        if not base_path.exists() or not base_path.is_dir():
            return result
            
        for item in base_path.iterdir():
            try:
                if item.is_dir():
                    child = build_directory_structure(item, max_depth, current_depth + 1)
                    result['children'].append(child)
                    result['size'] += child['size']
                else:
                    stat = item.stat()
                    file_info = {
                        'name': item.name,
                        'path': str(item),
                        'is_dir': False,
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'mime_type': get_mime_type(item)
                    }
                    result['children'].append(file_info)
                    result['size'] += file_info['size']
                    
            except (PermissionError, OSError) as e:
                logger.warning(f"Could not access {item}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error building directory structure for {base_path}: {e}")
        
    return result
