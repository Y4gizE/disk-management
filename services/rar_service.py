import os
import rarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from config import Config

class RarService:
    def __init__(self):
        self.shared_folder = Path(Config.SHARED_FOLDER)
        self.temp_dir = Path(tempfile.gettempdir()) / "disk_management_rar"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if rarfile is available
        if not Config.HAS_RARFILE:
            print("UYARI: RAR dosyalarını işleyebilmek için 'rarfile' kütüphanesi yüklü değil.")
            print("Yüklemek için: pip install rarfile")
    
    def get_archive_contents(self, archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
        """Get contents of a RAR archive with hierarchical structure."""
        if not Config.HAS_RARFILE:
            return None
            
        return self._get_archive_contents_local(archive_path, subpath)
    
    def _get_archive_contents_local(self, archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
        """Get archive contents using local rarfile library."""
        try:
            archive_path = Path(archive_path)
            if not archive_path.exists() or not archive_path.is_file():
                print(f"Arşiv bulunamadı: {archive_path}")
                return None
                
            contents = []
            processed_dirs = set()
            
            try:
                rf = rarfile.RarFile(str(archive_path), 'r')
                    
                for file_info in rf.infolist():
                    if file_info.isdir():
                        continue
                        
                    file_path = file_info.filename.replace('\\', '/')
                    
                    # Skip if not in the requested subdirectory
                    if subpath and not file_path.startswith(subpath):
                        continue
                        
                    # Build directory structure
                    dir_path = os.path.dirname(file_path)
                    
                    # Add parent directories to contents if not already added
                    parts = dir_path.split('/')
                    current_path = ''
                    
                    for part in parts:
                        if not part:
                            continue
                            
                        current_path = os.path.join(current_path, part) if current_path else part
                        
                        if current_path not in processed_dirs:
                            contents.append({
                                'name': part,
                                'path': current_path,
                                'is_dir': True,
                                'size': 0,
                                'modified': datetime.timestamp(datetime.now())
                            })
                            processed_dirs.add(current_path)
                    
                    # Add file to contents
                    if file_path not in processed_dirs:
                        contents.append({
                            'name': os.path.basename(file_path),
                            'path': file_path,
                            'is_dir': False,
                            'size': file_info.file_size,
                            'modified': datetime.timestamp(datetime(*file_info.date_time[:6]))
                        })
                
                return {
                    'success': True,
                    'name': archive_path.name,
                    'path': str(archive_path.relative_to(self.shared_folder)),
                    'is_dir': False,
                    'contents': contents,
                    'modified': datetime.timestamp(datetime.fromtimestamp(archive_path.stat().st_mtime))
                }
                
            except (rarfile.BadRarFile, rarfile.NotRarFile) as e:
                print(f"Hatalı RAR dosyası: {str(e)}")
                return None
                
        except Exception as e:
            print(f"RAR dosyası işlenirken hata oluştu: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_archive_contents_docker(self, archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
        """Get archive contents using the Docker-based RAR processor."""
        if not self.processor_enabled or not self.check_rar_processor():
            return self._get_archive_contents_local(archive_path, subpath)
            
        try:
            # Convert to relative path for the container
            rel_path = os.path.relpath(archive_path, self.shared_folder)
            container_path = f"/shared/{rel_path.replace(os.sep, '/')}"
            
            response = requests.post(
                f"{self.processor_url}/list",
                json={
                    "file_path": container_path,
                    "subpath": subpath
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    # Convert timestamps to datetime objects
                    for item in result.get('contents', []):
                        if item.get('date'):
                            try:
                                item['date'] = datetime.fromtimestamp(item['date'])
                            except (TypeError, ValueError):
                                item['date'] = datetime.now()
                    return result
            
            print(f"Docker RAR işlemci hatası: {response.status_code} - {response.text}")
            # Fall back to local extraction if Docker fails
            return self._get_archive_contents_local(archive_path, subpath)
            
        except requests.exceptions.RequestException as e:
            print(f"RAR işlemci ile iletişim hatası: {str(e)}")
            # Fall back to local extraction if Docker fails
            return self._get_archive_contents_local(archive_path, subpath)
        except Exception as e:
            print(f"Beklenmeyen hata: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._get_archive_contents_local(archive_path, subpath)
    
    def extract_archive(self, archive_path: str, output_dir: str = None, password: str = None) -> Tuple[bool, str]:
        """Extract a RAR archive to the specified directory."""
        try:
            archive_path = Path(archive_path)
            if not output_dir:
                output_dir = self.temp_dir / archive_path.stem
            else:
                output_dir = Path(output_dir)
                
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Try local extraction first
            if HAS_UNRAR or HAS_RARFILE:
                try:
                    if HAS_UNRAR:
                        rf = unrar_rarfile.RarFile(str(archive_path), 'r', pwd=password)
                    else:
                        rf = rarfile.RarFile(str(archive_path), 'r')
                        if password:
                            rf.setpassword(password)
                    rf.extractall(path=str(output_dir))
                    return True, str(output_dir)
                except Exception as e:
                    print(f"Yerel çıkarma başarısız: {str(e)}")
            
            # Fall back to Docker processor if local extraction failed
            if self.processor_enabled and self.check_rar_processor():
                try:
                    rel_path = os.path.relpath(archive_path, self.shared_folder)
                    container_path = f"/shared/{rel_path.replace(os.sep, '/')}"
                    
                    response = requests.post(
                        f"{self.processor_url}/extract",
                        json={
                            "file_path": container_path,
                            "output_dir": "/extracted"
                        },
                        timeout=self.timeout
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get('success'):
                            return True, result.get('output_dir', str(output_dir))
                    
                    print(f"Docker RAR çıkarma hatası: {response.status_code} - {response.text}")
                    
                except requests.exceptions.RequestException as e:
                    print(f"RAR işlemci ile iletişim hatası: {str(e)}")
            
            return False, "RAR dosyası çıkarılamadı. Lütfen doğru şifreyi girdiğinizden emin olun."
            
        except Exception as e:
            print(f"Çıkarma işlemi sırasında hata: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, str(e)
