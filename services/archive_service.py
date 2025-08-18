
import os
import zipfile
import rarfile
from datetime import datetime
from typing import Dict, Any, Optional, List
from config import Config
from utils.helpers import build_directory_structure

class ArchiveService:
    def __init__(self, rar_service=None):
        self.rar_service = rar_service
    
    def get_archive_contents(self, archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
        """
        Get contents of a ZIP or RAR archive with hierarchical structure.
        
        Args:
            archive_path: Path to the archive file
            subpath: Path within the archive to list contents for
            
        Returns:
            Dict containing archive metadata and contents, or None if unsupported
        """
        if not os.path.isfile(archive_path):
            print(f"File not found: {archive_path}")
            return None
        
        # Normalize subpath
        subpath = subpath.strip('/')
        
        # Check file type and delegate to appropriate handler
        if archive_path.lower().endswith('.rar'):
            return self._handle_rar_archive(archive_path, subpath)
        elif archive_path.lower().endswith('.zip'):
            return self._handle_zip_archive(archive_path, subpath)
        else:
            print(f"Unsupported archive format: {archive_path}")
            return None
    
    def _handle_zip_archive(self, archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
        """Handle ZIP archive processing"""
        try:
            entries = []
            total_size = 0
            file_count = 0
            
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                for item in zip_ref.infolist():
                    try:
                        # Skip directories
                        if item.filename.endswith('/'):
                            continue
                            
                        rel_path = item.filename.replace('\\', '/').rstrip('/')
                        
                        # Filter by subpath
                        if subpath and not (rel_path == subpath or rel_path.startswith(f"{subpath}/")):
                            continue
                            
                        display_path = rel_path[len(subpath)+1:] if subpath else rel_path
                        path_parts = display_path.split('/')
                        
                        # Add directory entries
                        self._add_directory_entries(entries, path_parts[:-1], subpath, item)
                        
                        # Add file entry
                        if path_parts[-1]:
                            total_size += item.file_size
                            file_count += 1
                            
                            entries.append({
                                'name': path_parts[-1],
                                'path': rel_path,
                                'size': item.file_size,
                                'compressed_size': item.compress_size,
                                'date': datetime(*item.date_time) if hasattr(item, 'date_time') else None,
                                'is_dir': False
                            })
                            
                    except Exception as e:
                        print(f"Error processing ZIP entry {item.filename}: {str(e)}")
                        continue
            
            return self._build_archive_result(entries, total_size, file_count, subpath, False)
                        
        except zipfile.BadZipFile as e:
            print(f"Bad ZIP file {archive_path}: {str(e)}")
            return None
        except Exception as e:
            print(f"Error reading ZIP file {archive_path}: {str(e)}")
            return None
    
    def _handle_rar_archive(self, archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
        """Handle RAR archive processing"""
        # Try Docker RAR processor first if available
        if self.rar_service and Config.RAR_PROCESSOR_ENABLED:
            result = self.rar_service.get_archive_contents_docker(archive_path, subpath)
            if result:
                return result
        
        # Fallback to local RAR processing
        return self._handle_rar_local(archive_path, subpath)
    
    def _handle_rar_local(self, archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
        """Handle RAR archive with local rarfile library"""
        try:
            if not os.access(archive_path, os.R_OK):
                print(f"No read permissions for RAR file: {archive_path}")
                return None
                
            file_size = os.path.getsize(archive_path)
            if file_size == 0:
                print(f"Empty RAR file: {archive_path}")
                return None
            
            entries = []
            total_size = 0
            file_count = 0
            
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                if rar_ref.needs_password():
                    print(f"Password-protected RAR files are not supported: {archive_path}")
                    return None
                    
                file_list = rar_ref.namelist()
                if not file_list:
                    print(f"Empty RAR archive: {archive_path}")
                    return None
                
                for item in rar_ref.infolist():
                    try:
                        # Skip directories
                        if item.isdir():
                            continue
                            
                        rel_path = item.filename.replace('\\', '/').rstrip('/')
                        
                        # Filter by subpath
                        if subpath and not (rel_path == subpath or rel_path.startswith(f"{subpath}/")):
                            continue
                            
                        display_path = rel_path[len(subpath)+1:] if subpath else rel_path
                        path_parts = display_path.split('/')
                        
                        # Add directory entries
                        self._add_directory_entries(entries, path_parts[:-1], subpath, item)
                        
                        # Add file entry
                        if path_parts[-1]:
                            total_size += item.file_size
                            file_count += 1
                            
                            entries.append({
                                'name': path_parts[-1],
                                'path': rel_path,
                                'size': item.file_size,
                                'compressed_size': getattr(item, 'compress_size', item.file_size),
                                'date': datetime.fromtimestamp(item.mtime) if hasattr(item, 'mtime') else None,
                                'is_dir': False
                            })
                            
                    except Exception as e:
                        print(f"Error processing RAR entry {item.filename}: {str(e)}")
                        continue
            
            return self._build_archive_result(entries, total_size, file_count, subpath, True)
                        
        except (rarfile.BadRarFile, rarfile.NotRarFile, rarfile.RarCannotExec) as e:
            print(f"Error processing RAR file {archive_path}: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error processing RAR file {archive_path}: {str(e)}")
            return None
    
    def _add_directory_entries(self, entries: List[Dict], path_parts: List[str], subpath: str, item):
        """Add directory entries for the given path parts"""
        current_path = []
        for part in path_parts:
            current_path.append(part)
            dir_path = '/'.join(current_path)
            
            # Check if directory already exists
            if not any(e['path'] == dir_path for e in entries):
                entries.append({
                    'name': part,
                    'path': f"{subpath}/{dir_path}" if subpath else dir_path,
                    'size': 0,
                    'compressed_size': 0,
                    'date': getattr(item, 'date_time', None) or getattr(item, 'mtime', None),
                    'is_dir': True
                })
    
    def _build_archive_result(self, entries: List[Dict], total_size: int, file_count: int, subpath: str, is_rar: bool) -> Dict[str, Any]:
        """Build the final result dictionary for archive contents"""
        # Build directory structure
        dir_structure = build_directory_structure(entries)
        
        # Prepare breadcrumbs
        breadcrumbs = []
        current_path = ''
        if subpath:
            parts = subpath.split('/')
            for i, part in enumerate(parts):
                if part:
                    current_path = current_path + '/' + part if current_path else part
                    breadcrumbs.append({
                        'name': part,
                        'path': current_path,
                        'is_last': i == len(parts) - 1
                    })
        
        return {
            'success': True,
            'contents': entries,
            'directory_structure': dir_structure,
            'breadcrumbs': breadcrumbs,
            'file_count': file_count,
            'total_size': total_size,
            'current_path': subpath,
            'parent_path': os.path.dirname(subpath.rstrip('/')) if subpath else '',
            'is_root': not bool(subpath),
            'is_rar': is_rar
        }
