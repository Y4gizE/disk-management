import os
import zipfile
import rarfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from config import Config
from utils.helpers import build_directory_structure


class ArchiveService:
    """Service for handling archive file operations (ZIP, RAR)."""
    
    def __init__(self, rar_service=None):
        """Initialize the ArchiveService.
        
        Args:
            rar_service: Optional RAR service for handling RAR files
        """
        self.rar_service = rar_service
        self.logger = logging.getLogger(__name__)
    
    def get_archive_contents(self, archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
        """Get contents of a ZIP or RAR archive with hierarchical structure.
        
        Args:
            archive_path: Path to the archive file
            subpath: Path within the archive to list contents for
            
        Returns:
            Dict containing archive metadata and contents, or None if unsupported
        """
        try:
            archive_path = Path(archive_path).resolve()
            if not archive_path.is_file():
                self.logger.error(f"File not found: {archive_path}")
                return None
            
            # Normalize subpath
            subpath = subpath.strip('/')
            
            # Delegate to appropriate handler based on file extension
            if str(archive_path).lower().endswith('.rar'):
                return self._handle_rar_archive(archive_path, subpath)
            elif str(archive_path).lower().endswith('.zip'):
                return self._handle_zip_archive(archive_path, subpath)
            else:
                self.logger.warning(f"Unsupported archive format: {archive_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing archive {archive_path}: {str(e)}", exc_info=True)
            return None

    def _handle_zip_archive(self, archive_path: Path, subpath: str) -> Optional[Dict[str, Any]]:
        """Process a ZIP archive and return its contents.
        
        Args:
            archive_path: Path to the ZIP file
            subpath: Path within the archive to list contents for
            
        Returns:
            Dict containing archive contents and metadata
        """
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                return self._process_archive_contents(
                    archive_path=archive_path,
                    archive_ref=zip_ref,
                    subpath=subpath,
                    is_rar=False,
                    get_file_info=lambda item: {
                        'size': item.file_size,
                        'compressed_size': item.compress_size,
                        'date': datetime(*item.date_time) if hasattr(item, 'date_time') else None,
                        'is_dir': item.filename.endswith('/')
                    }
                )
        except zipfile.BadZipFile as e:
            self.logger.error(f"Bad ZIP file {archive_path}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error reading ZIP file {archive_path}: {str(e)}", exc_info=True)
            return None

    def _handle_rar_archive(self, archive_path: Path, subpath: str) -> Optional[Dict[str, Any]]:
        """Process a RAR archive and return its contents.
        
        Args:
            archive_path: Path to the RAR file
            subpath: Path within the archive to list contents for
            
        Returns:
            Dict containing archive contents and metadata
        """
        # Try Docker RAR processor first if available
        if self.rar_service and Config.RAR_PROCESSOR_ENABLED:
            result = self.rar_service.get_archive_contents_docker(str(archive_path), subpath)
            if result:
                return result
        
        # Fallback to local RAR processing
        return self._handle_rar_local(archive_path, subpath)

    def _handle_rar_local(self, archive_path: Path, subpath: str) -> Optional[Dict[str, Any]]:
        """Process a RAR archive using local rarfile library.
        
        Args:
            archive_path: Path to the RAR file
            subpath: Path within the archive to list contents for
            
        Returns:
            Dict containing archive contents and metadata
        """
        try:
            if not os.access(archive_path, os.R_OK):
                self.logger.error(f"No read permissions for RAR file: {archive_path}")
                return None
                
            if archive_path.stat().st_size == 0:
                self.logger.error(f"Empty RAR file: {archive_path}")
                return None
            
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                if rar_ref.needs_password():
                    self.logger.warning(f"Password-protected RAR files are not supported: {archive_path}")
                    return None
                
                return self._process_archive_contents(
                    archive_path=archive_path,
                    archive_ref=rar_ref,
                    subpath=subpath,
                    is_rar=True,
                    get_file_info=lambda item: {
                        'size': item.file_size,
                        'compressed_size': getattr(item, 'compress_size', item.file_size),
                        'date': datetime.fromtimestamp(item.mtime) if hasattr(item, 'mtime') else None,
                        'is_dir': item.isdir()
                    }
                )
                
        except (rarfile.BadRarFile, rarfile.NotRarFile, rarfile.RarCannotExec) as e:
            self.logger.error(f"Error processing RAR file {archive_path}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error processing RAR file {archive_path}: {str(e)}", exc_info=True)
            return None

    def _process_archive_contents(
        self, 
        archive_path: Path,
        archive_ref: Any,
        subpath: str,
        is_rar: bool,
        get_file_info: callable
    ) -> Optional[Dict[str, Any]]:
        """Common method to process archive contents.
        
        Args:
            archive_path: Path to the archive file
            archive_ref: The archive reference (ZipFile or RarFile)
            subpath: Path within the archive to list contents for
            is_rar: Whether this is a RAR archive
            get_file_info: Function to get file info from archive item
            
        Returns:
            Dict containing archive contents and metadata
        """
        entries = []
        total_size = 0
        file_count = 0
        
        try:
            for item in archive_ref.infolist():
                try:
                    file_info = get_file_info(item)
                    
                    # Skip directories for ZIP (handled by _add_directory_entries)
                    if not is_rar and file_info['is_dir']:
                        continue
                        
                    rel_path = item.filename.replace('\\', '/').rstrip('/')
                    
                    # Filter by subpath
                    if subpath and not (rel_path == subpath or rel_path.startswith(f"{subpath}/")):
                        continue
                        
                    display_path = rel_path[len(subpath)+1:] if subpath and rel_path != subpath else rel_path
                    path_parts = display_path.split('/')
                    
                    # Add directory entries for parent directories
                    if len(path_parts) > 1:
                        self._add_directory_entries(entries, path_parts[:-1], subpath, item, file_info['date'])
                    
                    # Add file entry (or directory for RAR)
                    if path_parts[-1] or (is_rar and file_info['is_dir'] and len(path_parts) == 1):
                        if not file_info['is_dir']:
                            total_size += file_info['size']
                            file_count += 1
                        
                        entries.append({
                            'name': path_parts[-1] if path_parts[-1] else path_parts[-2] + '/',
                            'path': rel_path,
                            'size': file_info['size'],
                            'compressed_size': file_info['compressed_size'],
                            'date': file_info['date'],
                            'is_dir': file_info['is_dir']
                        })
                        
                except Exception as e:
                    self.logger.error(f"Error processing archive entry {item.filename}: {str(e)}", exc_info=True)
                    continue
            
            return self._build_archive_result(entries, total_size, file_count, subpath, is_rar)
            
        except Exception as e:
            self.logger.error(f"Error processing archive {archive_path}: {str(e)}", exc_info=True)
            return None

    def _add_directory_entries(
        self, 
        entries: List[Dict], 
        path_parts: List[str], 
        subpath: str, 
        item: Any,
        default_date: Optional[datetime] = None
    ) -> None:
        """Add directory entries for the given path parts.
        
        Args:
            entries: List to add directory entries to
            path_parts: List of path components
            subpath: Current subpath within the archive
            item: Archive item for getting metadata
            default_date: Default date to use if not available in item
        """
        current_path = []
        for part in path_parts:
            if not part:
                continue
                
            current_path.append(part)
            dir_path = '/'.join(current_path)
            
            # Check if directory already exists
            if not any(e.get('path') == dir_path for e in entries):
                entries.append({
                    'name': part,
                    'path': f"{subpath}/{dir_path}" if subpath else dir_path,
                    'size': 0,
                    'compressed_size': 0,
                    'date': default_date,
                    'is_dir': True
                })

    def _build_archive_result(
        self, 
        entries: List[Dict], 
        total_size: int, 
        file_count: int, 
        subpath: str, 
        is_rar: bool
    ) -> Dict[str, Any]:
        """Build the final result dictionary for archive contents.
        
        Args:
            entries: List of file/directory entries
            total_size: Total size of all files in bytes
            file_count: Number of files in the archive
            subpath: Current subpath within the archive
            is_rar: Whether this is a RAR archive
            
        Returns:
            Dict containing archive metadata and contents
        """
        # Build directory structure
        dir_structure = build_directory_structure(entries)
        
        # Prepare breadcrumbs
        breadcrumbs = []
        if subpath:
            parts = subpath.split('/')
            for i in range(len(parts)):
                breadcrumbs.append({
                    'name': parts[i],
                    'path': '/'.join(parts[:i+1])
                })
        
        return {
            'name': os.path.basename(subpath) if subpath else 'Root',
            'path': subpath,
            'is_dir': True,
            'size': total_size,
            'file_count': file_count,
            'is_rar': is_rar,
            'entries': entries,
            'dir_structure': dir_structure,
            'breadcrumbs': breadcrumbs
        }
