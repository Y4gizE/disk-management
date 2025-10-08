import os
import sys
import time
import json
import socket
import hashlib
import zipfile
import rarfile
import requests
import threading
import subprocess
import magic
import argparse
import shutil
import psutil
from datetime import datetime
from functools import wraps
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session, abort, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.serving import run_simple
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from zeroconf import ServiceInfo, Zeroconf, IPVersion
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import config after environment variables are loaded
from config import Config

try:
    import netifaces
    NETIFACES_AVAILABLE = True
except ImportError:
    NETIFACES_AVAILABLE = False
    print("Warning: netifaces not available. Some network features may be limited.")

# Global variable for public IP
PUBLIC_IP = None

# RAR Processor configuration
RAR_PROCESSOR_ENABLED = os.environ.get('RAR_PROCESSOR_ENABLED', 'false').lower() == 'true'
RAR_PROCESSOR_URL = os.environ.get('RAR_PROCESSOR_URL', 'http://localhost:5001')
RAR_PROCESSOR_CONTAINER_NAME = "rar-processor"

def check_rar_processor():
    """Check if the RAR processor service is running and accessible."""
    global RAR_PROCESSOR_ENABLED
    
    if not RAR_PROCESSOR_ENABLED:
        print("RAR processor is disabled by configuration")
        return False
        
    try:
        # Check if the RAR processor is accessible
        response = requests.get(f"{RAR_PROCESSOR_URL}/health", timeout=2)
        if response.status_code == 200:
            print("RAR processor is running and accessible")
            return True
            
    except requests.exceptions.RequestException as e:
        print(f"RAR processor is not accessible: {str(e)}")
        
    RAR_PROCESSOR_ENABLED = False
    print("RAR processor is not available. Some features may be limited.")
    return False

def get_archive_contents_docker(archive_path, subpath=''):
    """Get archive contents using the Docker-based RAR processor."""
    try:
        # Convert to relative path for the container
        rel_path = os.path.relpath(archive_path, SHARED_FOLDER)
        container_path = f"/shared/{rel_path.replace(os.sep, '/')}"
        
        response = requests.post(
            f"{RAR_PROCESSOR_URL}/list",
            json={
                "file_path": container_path,
                "subpath": subpath  # Pass the subpath to the processor
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                # Convert timestamps to datetime objects
                for item in result.get('contents', []):
                    if item.get('date'):
                        item['date'] = datetime.fromtimestamp(item['date'])
                return result
        
        print(f"Docker RAR processor error: {response.text}")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with RAR processor: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

from zeroconf import ServiceInfo, Zeroconf, IPVersion
from typing import List, Dict, Any, Optional, Union
import io
import tempfile
from pathlib import Path

# Constants
SHARED_FOLDER = os.path.join(str(Path.home()), 'Downloads', 'DiskStorage')
STORAGE_LIMIT = 5 * 1024 * 1024 * 1024  # 5GB in bytes
DEFAULT_PASSWORD = '1234'  # Default password

# Ensure shared folder exists
os.makedirs(SHARED_FOLDER, exist_ok=True)

from datetime import datetime

app = Flask(__name__, template_folder='templates')
CORS(app)
app.secret_key = os.urandom(24)  # For flash messages
app.config['PASSWORD_HASH'] = generate_password_hash('1234')  # Default password hash

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    error_trace = traceback.format_exc()
    print(f"\n=== ERROR ===\n{error_trace}\n==========\n")
    return f"""
    <h1>500 Internal Server Error</h1>
    <h3>{str(e)}</h3>
    <pre>{error_trace}</pre>
    <p><a href="{url_for('index')}">Return to home page</a></p>
    """, 500

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Ensure shared folder exists
os.makedirs(SHARED_FOLDER, exist_ok=True)

class FileChangeHandler(FileSystemEventHandler):
    """Handle file system change events"""
    def on_modified(self, event):
        if not event.is_directory:
            self.sync_file(event.src_path)
    
    def on_created(self, event):
        if not event.is_directory:
            self.sync_file(event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.notify_peers('delete', event.src_path)
    
    def sync_file(self, file_path):
        """Sync file changes to peer devices"""
        if os.path.isfile(file_path):
            self.notify_peers('update', file_path)
    
    def notify_peers(self, action, file_path):
        """Notify peer devices about file changes"""
        rel_path = os.path.relpath(file_path, SHARED_FOLDER)
        for device_id, device in DEVICES.items():
            if device_id != socket.gethostname():
                try:
                    # In a real app, send notification to peer's API
                    pass
                except Exception as e:
                    print(f"Error notifying {device_id}: {str(e)}")

# Start file system watcher
event_handler = FileChangeHandler()
observer = Observer()
observer.schedule(event_handler, SHARED_FOLDER, recursive=True)
observer.start()

def get_disk_usage():
    """Get current disk usage of shared folder"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(SHARED_FOLDER):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

def check_quota(file_size):
    """Check if adding file would exceed storage limit"""
    current_usage = get_disk_usage()
    return (current_usage + file_size) <= STORAGE_LIMIT, current_usage

# API Endpoints
@app.route('/api/disk_usage', methods=['GET'])
def get_disk_usage_info():
    """Get current disk usage information"""
    usage = get_disk_usage()
    return jsonify({
        'used': usage,
        'total': STORAGE_LIMIT,
        'free': max(0, STORAGE_LIMIT - usage),
        'usage_percent': (usage / STORAGE_LIMIT) * 100 if STORAGE_LIMIT > 0 else 0
    })

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload with quota checking"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Check file size against quota
    file.seek(0, 2)  # Go to end of file to get size
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    has_space, current_usage = check_quota(file_size)
    if not has_space:
        return jsonify({
            'error': 'Not enough disk space',
            'current_usage': current_usage,
            'requested': file_size,
            'available': max(0, STORAGE_LIMIT - current_usage)
        }), 507  # 507 Insufficient Storage
    
    # Save the file
    filename = os.path.join(SHARED_FOLDER, secure_filename(file.filename))
    try:
        file.save(filename)
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': file.filename,
            'size': file_size,
            'path': filename
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<path:filename>', methods=['GET'])
@login_required
def download_file(filename):
    """Download a file or folder from shared storage"""
    # Normalize the filename and handle Windows paths
    filename = filename.strip('/').replace('\\', '/')
    filepath = os.path.normpath(os.path.join(SHARED_FOLDER, filename)).replace('\\', '/')
    
    # Security check to prevent directory traversal
    shared_folder_abs = os.path.abspath(SHARED_FOLDER).replace('\\', '/')
    filepath_abs = os.path.abspath(filepath).replace('\\', '/')
    
    if not filepath_abs.startswith(shared_folder_abs):
        flash('Geçersiz dosya yolu', 'error')
        return redirect(url_for('index'))
    
    try:
        if os.path.isfile(filepath_abs):
            # Handle file download
            return send_file(
                filepath_abs,
                as_attachment=True,
                download_name=os.path.basename(filepath_abs)
            )
        elif os.path.isdir(filepath_abs):
            # Create a temporary file for the zip
            temp_file = io.BytesIO()
            
            # Create a zip file in memory
            with zipfile.ZipFile(temp_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                base_name = os.path.basename(filepath_abs.rstrip(os.sep))
                
                # Walk through the directory and add files to the zip
                for root, dirs, files in os.walk(filepath_abs):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Calculate the relative path for the zip file
                        rel_path = os.path.relpath(file_path, os.path.dirname(filepath_abs))
                        zipf.write(file_path, rel_path)
            
            # Move to the beginning of the BytesIO object
            temp_file.seek(0)
            
            # Send the zip file
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f"{base_name}.zip",
                mimetype='application/zip'
            )
        else:
            flash('Dosya veya klasör bulunamadı', 'error')
            return redirect(url_for('index'))
            
    except Exception as e:
        flash(f'Dosya indirilirken hata oluştu: {str(e)}', 'error')
        return redirect(url_for('index'))
        return redirect(url_for('index'))

@app.route('/delete/<path:filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    # Normalize the filename and handle Windows paths
    filename = filename.strip('/').replace('\\', '/')
    filepath = os.path.normpath(os.path.join(SHARED_FOLDER, filename)).replace('\\', '/')
    
    # Security check to prevent directory traversal
    shared_folder_abs = os.path.abspath(SHARED_FOLDER).replace('\\', '/')
    filepath_abs = os.path.abspath(filepath).replace('\\', '/')
    
    if not filepath_abs.startswith(shared_folder_abs) or not os.path.exists(filepath_abs):
        return jsonify({'success': False, 'error': 'Dosya veya klasör bulunamadı'}), 404
    
    try:
        if os.path.isfile(filepath_abs):
            os.remove(filepath_abs)
        else:
            shutil.rmtree(filepath_abs)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting {filepath_abs}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Custom Jinja2 filters
@app.template_filter('datetime')
def format_datetime(timestamp, format='%d.%m.%Y %H:%M:%S'):
    if timestamp is None:
        return "-"
    try:
        # If timestamp is already a datetime object, format it directly
        if hasattr(timestamp, 'strftime'):
            return timestamp.strftime(format)
        # If timestamp is a string, try to convert it to float first
        if isinstance(timestamp, str):
            try:
                timestamp = float(timestamp)
            except (ValueError, TypeError):
                return str(timestamp)  # Return as is if can't convert to number
        # Convert timestamp to datetime and format
        return datetime.fromtimestamp(float(timestamp)).strftime(format)
    except (ValueError, TypeError) as e:
        print(f"Error formatting timestamp {timestamp}: {e}")
        return str(timestamp)  # Return original value if conversion fails

# Global variables
DEVICES = {}
SHARED_FOLDERS = {}
HOST_IP = '0.0.0.0'
RELAY_SERVERS = [
    {'url': 'http://relay1.example.com:5000', 'status': 'unknown'},
    {'url': 'http://relay2.example.com:5000', 'status': 'unknown'}
]
DEFAULT_PORT = 5000
SERVICE_NAME = "DiskStorage"
SERVICE_TYPE = "_http._tcp.local."
zeroconf = None
service_info = None

class Device:
    def __init__(self, device_id, ip, port, shared_folders):
        self.device_id = device_id
        self.ip = ip
        self.port = port
        self.shared_folders = shared_folders or []
        self.last_seen = time.time()

    def to_dict(self):
        return {
            'device_id': self.device_id,
            'ip': self.ip,
            'port': self.port,
            'shared_folders': self.shared_folders,
            'last_seen': self.last_seen
        }

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Import the LoginForm at the top of the file with other imports
from forms import LoginForm

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    
    if form.validate_on_submit():
        if check_password_hash(app.config['PASSWORD_HASH'], form.password.data):
            session['authenticated'] = True
            session.permanent = True  # Make the session permanent
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid password', 'error')
    
    return render_template('auth/login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

# Helper function to get file info
def get_folder_size(folder_path):
    """Calculate the total size of a folder and all its contents."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # Skip if it's a symlink or inaccessible
            if not os.path.islink(fp):
                try:
                    total_size += os.path.getsize(fp)
                except (OSError, PermissionError):
                    continue
    return total_size

def format_size(size_bytes):
    """Convert size in bytes to human-readable format."""
    if not size_bytes:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            if unit == 'B':
                return f"{int(size_bytes)} {unit}"
            else:
                return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def build_directory_structure(entries):
    """Build a hierarchical directory structure from a flat list of file paths."""
    root = {'name': '', 'children': [], 'is_dir': True, 'path': ''}
    
    for entry in entries:
        path_parts = entry['path'].split('/')
        current = root
        current_path = []
        
        for i, part in enumerate(path_parts):
            current_path.append(part)
            path = '/'.join(current_path)
            
            # Skip empty parts (can happen with leading/trailing slashes)
            if not part:
                continue
                
            # Find or create the directory entry
            found = False
            for child in current['children']:
                if child['name'] == part and child['is_dir']:
                    current = child
                    found = True
                    break
            
            if not found:
                is_dir = i < len(path_parts) - 1 or entry.get('is_dir', False)
                new_node = {
                    'name': part,
                    'children': [],
                    'is_dir': is_dir,
                    'path': path,
                    'size': 0,
                    'date': None
                }
                
                if not is_dir:
                    new_node.update({
                        'size': entry.get('size', 0),
                        'date': entry.get('date')
                    })
                
                current['children'].append(new_node)
                current = new_node
    
    return root

def get_zip_contents(archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
    """
    Get contents of a ZIP archive with hierarchical structure.
    
    Args:
        archive_path: Path to the ZIP file
        subpath: Path within the archive to list contents for
        
    Returns:
        Dict containing archive metadata and contents, or None if there's an error
    """
    if not os.path.isfile(archive_path):
        print(f"ZIP file not found: {archive_path}")
        return None
    
    try:
        entries = []
        dir_structure = {'name': '', 'path': '', 'children': []}
        breadcrumbs = []
        seen_dirs = set()
        
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            # First pass: collect all files and directories
            all_files = []
            for item in zip_ref.infolist():
                # Skip directory entries (they're handled by the file paths)
                if item.filename.endswith('/'):
                    continue
                    
                # Normalize the path
                rel_path = item.filename.replace('\\', '/').rstrip('/')
                all_files.append((rel_path, item))
            
            # Second pass: process files and build directory structure
            for rel_path, item in all_files:
                try:
                    # Skip if not in the current subpath
                    if subpath and not (rel_path == subpath or rel_path.startswith(f"{subpath}/")):
                        continue
                    
                    # Split the path into components
                    path_parts = rel_path.split('/')
                    
                    # Calculate the display path (relative to subpath)
                    if subpath:
                        display_parts = rel_path[len(subpath):].strip('/').split('/')
                        if not display_parts or not display_parts[0]:
                            continue
                    else:
                        display_parts = path_parts
                    
                    # Handle the current directory level
                    current_dir = ''
                    
                    # Add parent directory entry if we're in a subdirectory
                    if len(display_parts) > 1:
                        dir_name = display_parts[0]
                        dir_path = f"{subpath}/{dir_name}" if subpath else dir_name
                        
                        # Add directory entry if not already added
                        if dir_path not in seen_dirs:
                            entries.append({
                                'name': dir_name,
                                'path': dir_path,
                                'size': 0,
                                'modified': 0,
                                'is_dir': True
                            })
                            seen_dirs.add(dir_path)
                    
                    # Add the file entry (if it's a direct child of the current subpath)
                    if len(display_parts) == 1 or (subpath and rel_path.startswith(subpath)):
                        # Get file modification time
                        modified = 0
                        if hasattr(item, 'date_time') and item.date_time and len(item.date_time) >= 6:
                            try:
                                dt = datetime(*item.date_time[:6])
                                modified = int(dt.timestamp())
                            except (TypeError, ValueError):
                                pass
                        
                        entries.append({
                            'name': display_parts[-1],
                            'path': rel_path,
                            'size': item.file_size,
                            'modified': modified,
                            'is_dir': False,
                            'compressed_size': item.compress_size
                        })
                
                except Exception as e:
                    print(f"Error processing ZIP entry {rel_path}: {str(e)}")
                    continue
        
        # Build breadcrumbs if we're in a subdirectory
        if subpath:
            parts = subpath.split('/')
            current_path = ''
            for i, part in enumerate(parts):
                if part:  # Skip empty parts
                    current_path = f"{current_path}/{part}" if current_path else part
                    breadcrumbs.append({
                        'name': part,
                        'path': current_path
                    })
        
        # Sort entries: directories first, then files, both alphabetically
        entries.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        
        return {
            'success': True,
            'contents': entries,
            'file_count': len([e for e in entries if not e['is_dir']]),
            'total_size': sum(e.get('size', 0) for e in entries if not e.get('is_dir', False)),
            'is_rar': False,
            'breadcrumbs': breadcrumbs,
            'parent_path': '/'.join(subpath.split('/')[:-1]) if '/' in subpath else ''
        }
        
    except Exception as e:
        print(f"Error processing ZIP file: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_rar_contents(archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
    """
    Get contents of a RAR archive with hierarchical structure.
    
    Args:
        archive_path: Path to the RAR file
        subpath: Path within the archive to list contents for
        
    Returns:
        Dict containing archive metadata and contents, or None if there's an error
    """
    if not os.path.isfile(archive_path):
        print(f"RAR file not found: {archive_path}")
        return None
    
    # First check if RAR processing is available
    if not (Config.HAS_RARFILE or Config.HAS_UNRAR):
        print("RAR desteği yok. Lütfen 'rarfile' veya 'unrar' kütüphanelerinden birini yükleyin.")
        return None
        
    from services.rar_service import RarService
    rar_service = RarService()
    
    try:
        # Get archive contents using the service
        result = rar_service.get_archive_contents(archive_path, subpath)
        
        if not result or not result.get('success'):
            print(f"Failed to read RAR archive contents: {result}")
            return None
        
        # Process the result to match our template format
        contents = []
        for item in result.get('contents', []):
            contents.append({
                'name': item.get('name', ''),
                'size': item.get('size', 0),
                'compressed_size': item.get('compressed_size', item.get('size', 0)),
                'is_dir': item.get('is_dir', False),
                'modified': item.get('date') or item.get('modified', 0),
                'path': item.get('path', item.get('name', ''))
            })
        
        return {
            'success': True,
            'contents': contents,
            'file_count': len(contents),
            'total_size': sum(f.get('size', 0) for f in contents),
            'is_rar': True
        }
    
    except Exception as e:
        print(f"Error processing RAR file: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_archive_contents(archive_path: str, subpath: str = '') -> Optional[Dict[str, Any]]:
    """
    Get contents of a ZIP or RAR archive with hierarchical structure.
    
    Args:
        archive_path: Path to the archive file
        subpath: Path within the archive to list contents for
        
    Returns:
        Dict containing archive metadata and contents, or None if the file is not a supported archive
    """
    if not os.path.isfile(archive_path):
        print(f"File not found: {archive_path}")
        return None
    
    try:
        # Handle RAR files
        if archive_path.lower().endswith('.rar'):
            return get_rar_contents(archive_path, subpath)
        # Handle ZIP files
        elif archive_path.lower().endswith('.zip'):
            return get_zip_contents(archive_path, subpath)
        else:
            print(f"Unsupported archive format: {archive_path}")
            return None
            
    except Exception as e:
        print(f"Error in get_archive_contents: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_file_info(file_path: str, base_path: str = None) -> dict:
    """
    Get information about a file or directory.
    
    Args:
        file_path: Path to the file or directory
        base_path: Base path to calculate relative path from (defaults to SHARED_FOLDER)
        
    Returns:
        Dict containing file information
    """
    if base_path is None:
        base_path = SHARED_FOLDER
        
    try:
        # Convert to absolute path and normalize
        file_path_abs = os.path.abspath(file_path).replace('\\', '/')
        
        # Get relative path for display
        rel_path = os.path.relpath(file_path_abs, SHARED_FOLDER).replace('\\', '/')
        
        # Get file stats
        stat_info = os.stat(file_path_abs)
        
        # Determine if it's a directory or file
        is_dir = os.path.isdir(file_path_abs)
        
        # Prepare basic file info
        file_info = {
            'name': os.path.basename(file_path_abs),
            'path': rel_path,
            'is_dir': is_dir,
            'size': 0,
            'size_formatted': '0 B',
            'modified': datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'relative_path': rel_path
        }
        
        # Get size (recursive for directories)
        if is_dir:
            dir_size = get_folder_size(file_path_abs)
            file_info['size'] = dir_size
            file_info['size_formatted'] = format_size(dir_size)
        else:
            file_info['size'] = stat_info.st_size
            file_info['size_formatted'] = format_size(stat_info.st_size)
        
        # Get file type using python-magic
        try:
            mime = magic.Magic(mime=True)
            file_type = mime.from_file(file_path_abs)
            file_info['type'] = file_type
            
            # For better display, get human-readable type
            if is_dir:
                file_info['type'] = 'folder'
            elif file_type.startswith('image/'):
                file_info['type'] = 'image'
            elif file_type == 'application/pdf':
                file_info['type'] = 'pdf'
            elif file_type in ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed']:
                file_info['type'] = 'archive'
            else:
                # Get the file extension for other types
                _, ext = os.path.splitext(file_path_abs)
                file_info['type'] = ext[1:].lower() if ext else 'file'
                
        except Exception as e:
            print(f"Error getting file type for {file_path_abs}: {str(e)}")
            file_info['type'] = 'file'
        
        return file_info
        
    except Exception as e:
        print(f"Error in get_file_info for {file_path}: {str(e)}")
        # Return minimal info if there's an error
        return {
            'name': os.path.basename(file_path),
            'path': file_path,
            'is_dir': False,
            'size': 0,
            'size_formatted': '0 B',
            'modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'unknown',
            'relative_path': os.path.relpath(file_path, base_path) if base_path else file_path
        }

# Web Interface
@app.route('/')
@app.route('/<path:subpath>')
@login_required
def index(subpath=''):
    # Trigger device discovery in the background
    discovery_thread = threading.Thread(target=discover_devices)
    discovery_thread.daemon = True
    discovery_thread.start()
    
    # Normalize the subpath and handle Windows paths
    subpath = subpath.strip('/').replace('\\', '/')
    
    # Build the full path and ensure it's within the shared folder
    current_path = os.path.normpath(os.path.join(SHARED_FOLDER, subpath)).replace('\\', '/')
    
    # Security check to prevent directory traversal
    shared_folder_abs = os.path.abspath(SHARED_FOLDER).replace('\\', '/')
    current_path_abs = os.path.abspath(current_path).replace('\\', '/')
    
    if not current_path_abs.startswith(shared_folder_abs):
        abort(403)  # Forbidden
    
    # Check if the path exists and is a directory
    if not os.path.exists(current_path_abs):
        abort(404)  # Not found
        
    if not os.path.isdir(current_path_abs):
        # If it's a file, serve it directly
        rel_path = os.path.relpath(current_path_abs, SHARED_FOLDER).replace('\\', '/')
        return download_file(rel_path)
    
    # Get list of files and directories in the current path
    files = []
    breadcrumbs = [{'name': 'Ana Dizin', 'path': ''}]
    
    try:
        # Build breadcrumbs
        if subpath:
            path_parts = subpath.split('/')
            current_breadcrumb_path = ''
            
            for part in path_parts:
                if not part:
                    continue
                if current_breadcrumb_path:
                    current_breadcrumb_path = f"{current_breadcrumb_path}/{part}"
                else:
                    current_breadcrumb_path = part
                breadcrumbs.append({'name': part, 'path': current_breadcrumb_path})
        
        # List directory contents
        for item in sorted(os.listdir(current_path_abs)):
            item_path = os.path.join(current_path_abs, item).replace('\\', '/')
            if os.path.isfile(item_path) or os.path.isdir(item_path):
                files.append(get_file_info(item_path, current_path_abs))
        
        # Sort: directories first, then files, both alphabetically
        files.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        
    except Exception as e:
        print(f"Error listing files: {e}")
        abort(500)  # Internal Server Error
    
    # Get local IP for sharing
    local_ip = get_local_ip()
    port = request.host.split(':')[-1] if ':' in request.host else '5000'
    
    return render_template('index.html', 
                         files=files, 
                         local_ip=local_ip, 
                         port=port,
                         public_ip=PUBLIC_IP or 'Not available',
                         current_path=subpath,
                         breadcrumbs=breadcrumbs)

@app.route('/view-image/<path:filename>')
@login_required
def view_image_route(filename):
    """View an image file in a dedicated viewer."""
    filepath = os.path.join(SHARED_FOLDER, filename)
    if not os.path.isfile(filepath):
        abort(404)
    
    # Check if the file is an image
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
    if not any(filename.lower().endswith(ext) for ext in image_extensions):
        abort(400, "Not an image file")
    
    return render_template('image_viewer.html',
                         title=os.path.basename(filename),
                         file_path=filename)

@app.route('/view-pdf/<path:filename>')
@login_required
def view_pdf_route(filename):
    """View a PDF file in a dedicated viewer."""
    filepath = os.path.join(SHARED_FOLDER, filename)
    if not os.path.isfile(filepath):
        abort(404)
    
    # Check if the file is a PDF
    if not filename.lower().endswith('.pdf'):
        abort(400, "Not a PDF file")
    
    return render_template('pdf_viewer.html',
                         title=os.path.basename(filename),
                         file_path=filename)

@app.route('/view-archive/<path:filename>', defaults={'subpath': ''})
@app.route('/view-archive/<path:filename>/<path:subpath>')
@login_required
def view_archive(filename, subpath=''):
    """View the contents of a ZIP or RAR archive, optionally within a subdirectory."""
    try:
        # Ensure the file exists and is within the shared folder
        filepath = os.path.join(SHARED_FOLDER, filename)
        if not os.path.isfile(filepath):
            flash('Dosya bulunamadı.', 'error')
            return redirect(url_for('index'))
        
        # Normalize subpath to remove any leading/trailing slashes
        subpath = subpath.strip('/')
        
        # Check if the file is an archive
        if not (filename.lower().endswith(('.zip', '.rar'))):
            flash('Desteklenmeyen arşiv formatı.', 'error')
            return redirect(url_for('index'))
        
        # Handle RAR files
        if filename.lower().endswith('.rar'):
            archive_data = get_rar_contents(filepath, subpath)
        # Handle ZIP files
        else:
            archive_data = get_zip_contents(filepath, subpath)
        
        if not archive_data or not archive_data.get('success'):
            flash('Arşiv dosyası okunamadı veya bozuk olabilir.', 'error')
            return redirect(url_for('index'))
        
        # Prepare the template context
        context = {
            'title': os.path.basename(filename),
            'archive_name': os.path.basename(filename),
            'file_path': filename,
            'contents': archive_data.get('contents', []),
            'file_count': archive_data.get('file_count', 0),
            'total_size': archive_data.get('total_size', 0),
            'is_rar': archive_data.get('is_rar', False),
            'show_rar_contents': archive_data.get('is_rar', False),
            'subpath': subpath,
            'parent_path': archive_data.get('parent_path', ''),
            'breadcrumbs': archive_data.get('breadcrumbs', []),
            'has_parent': bool(subpath),
            'format_size': format_size
        }
        
        return render_template('archive_viewer.html', **context)
        
    except Exception as e:
        print(f"Error in view_archive: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Arşiv görüntülenirken bir hata oluştu: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/view/<path:filename>')
@login_required
def view_file(filename):
    """View a file in the appropriate viewer based on its type."""
    filepath = os.path.join(SHARED_FOLDER, filename)
    if not os.path.isfile(filepath):
        abort(404)
    
    # Check if it's an archive file
    archive_data = get_archive_contents(filepath)
    if archive_data:
        return redirect(url_for('view_archive', filename=filename))
    
    # Determine the file type and redirect to the appropriate viewer
    filename_lower = filename.lower()
    
    # Image files
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
    if any(filename_lower.endswith(ext) for ext in image_extensions):
        return redirect(url_for('view_image_route', filename=filename))
    
    # PDF files
    elif filename_lower.endswith('.pdf'):
        return redirect(url_for('view_pdf_route', filename=filename))
    
    # Text files (fallback)
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return render_template('viewer.html', 
                            filename=filename, 
                            content=content)
    except:
        return "Cannot display file content (binary or unsupported encoding)"

@app.route('/share', methods=['GET', 'POST'])
@login_required
def share():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        try:
            filepath = os.path.join(SHARED_FOLDER, secure_filename(file.filename))
            file.save(filepath)
            flash('File shared successfully!', 'success')
        except Exception as e:
            flash(f'Error sharing file: {str(e)}', 'error')
        
        return redirect(url_for('share'))
    
    return render_template('share.html')
    
    # Convert Device objects to dictionaries for the template
    devices_list = [device.to_dict() for device in DEVICES.values()]
    return render_template('index.html', devices=devices_list)

@app.route('/register_device_ui', methods=['GET', 'POST'])
def register_device_ui():
    """Cihaz kayıt formu"""
    if request.method == 'POST':
        device_id = request.form.get('device_id')
        port = request.form.get('port', DEFAULT_PORT)
        shared_folder = request.form.get('shared_folder', '')
        
        if not device_id:
            return "Cihaz ID'si gerekli", 400
            
        shared_folders = [f.strip() for f in shared_folder.split(',') if f.strip()]
        
        # Register the device
        data = {
            'device_id': device_id,
            'port': port,
            'shared_folders': shared_folders
        }
        
        # Call the API endpoint
        response = app.test_client().post(
            '/register',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        if response.status_code == 200:
            return redirect(url_for('index'))
        else:
            return f"Hata oluştu: {response.data.decode()}", 400
    
    return render_template('register.html')

# API Endpoints
@app.route('/register', methods=['POST'])
def register_device():
    data = request.json
    device_id = data.get('device_id')
    ip = request.remote_addr
    port = data.get('port', DEFAULT_PORT)
    shared_folders = data.get('shared_folders', [])
    
    if not device_id:
        return jsonify({'error': 'Device ID is required'}), 400
    
    DEVICES[device_id] = Device(device_id, ip, port, shared_folders)
    return jsonify({'status': 'success', 'message': f'Device {device_id} registered'})

@app.route('/api/devices', methods=['GET'])
def list_devices():
    """List all discovered devices"""
    try:
        # Trigger a new discovery in the background
        discovery_thread = threading.Thread(target=discover_devices)
        discovery_thread.daemon = True
        discovery_thread.start()
        
        # Clean up old devices (not seen in last 5 minutes)
        current_time = time.time()
        devices_to_remove = []
        
        for device_name, device in list(DEVICES.items()):
            if current_time - device.last_seen > 300:  # 5 minutes
                devices_to_remove.append(device_name)
        
        for device_name in devices_to_remove:
            del DEVICES[device_name]
        
        # Convert to list of dictionaries for JSON serialization
        devices_list = [{
            'device_id': device.device_id,
            'ip': device.ip,
            'port': device.port,
            'shared_folders': device.shared_folders,
            'last_seen': device.last_seen,
            'status': 'online' if (current_time - device.last_seen) < 60 else 'offline'
        } for device in DEVICES.values()]
        
        return jsonify({
            'status': 'success',
            'devices': devices_list,
            'count': len(devices_list)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/share', methods=['POST'])
def share_folder():
    data = request.json
    device_id = data.get('device_id')
    folder_path = data.get('folder_path')
    
    if not device_id or not folder_path:
        return jsonify({'error': 'Device ID and folder path are required'}), 400
    
    if device_id not in DEVICES:
        return jsonify({'error': 'Device not found'}), 404
    
    # Convert to absolute path
    abs_path = str(Path(folder_path).absolute())
    
    if not Path(abs_path).exists() or not Path(abs_path).is_dir():
        return jsonify({'error': 'Invalid folder path'}), 400
    
    if device_id not in SHARED_FOLDERS:
        SHARED_FOLDERS[device_id] = []
    
    if abs_path not in SHARED_FOLDERS[device_id]:
        SHARED_FOLDERS[device_id].append(abs_path)
    
    return jsonify({
        'status': 'success',
        'message': f'Folder {abs_path} shared by {device_id}'
    })

def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        if NETIFACES_AVAILABLE:
            # Try to get IP using netifaces if available
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        if ip != '127.0.0.1':
                            return ip
    except Exception as e:
        print(f"Error getting local IP with netifaces: {e}")
    
    # Fallback method 1: Try to connect to an external server
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        print(f"Error getting local IP with socket: {e}")
    
    # Fallback method 2: Using hostname
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if not local_ip.startswith('127.'):
            return local_ip
    except Exception as e:
        print(f"Error getting local IP with hostname: {e}")
    
    return '127.0.0.1'

def start_zeroconf_service(port):
    """Start the ZeroConf service for network discovery"""
    global zeroconf, service_info
    
    try:
        # Get local IP address
        local_ip = get_local_ip()
        
        # Create service info
        service_name = f"{SERVICE_NAME} {socket.gethostname()}"
        service_name = service_name.replace(' ', '-') + "." + SERVICE_TYPE
        
        desc = {
            'version': '1.0',
            'hostname': socket.gethostname(),
            'port': port,
            'ip': local_ip
        }
        
        service_info = ServiceInfo(
            SERVICE_TYPE,
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties=desc,
            server=socket.gethostname() + ".local.",
        )
        
        # Register the service
        zeroconf = Zeroconf()
        zeroconf.register_service(service_info)
        print(f"ZeroConf service registered: {service_name} at {local_ip}:{port}")
        
    except Exception as e:
        print(f"Error starting ZeroConf service: {e}")

def stop_zeroconf_service():
    """Stop the ZeroConf service"""
    global zeroconf
    if zeroconf:
        zeroconf.unregister_all_services()
        zeroconf.close()
        print("ZeroConf service stopped")

def discover_devices():
    """Discover other devices on the local network"""
    from zeroconf import ServiceBrowser, Zeroconf
    
    class MyListener:
        def remove_service(self, zeroconf, type, name):
            print(f"Service {name} removed")
            
        def add_service(self, zeroconf, type, name):
            info = zeroconf.get_service_info(type, name)
            if info:
                address = socket.inet_ntoa(info.addresses[0])
                port = info.port
                device_name = name.split('.')[0]
                
                print(f"Discovered device: {device_name} at {address}:{port}")
                
                # Add to discovered devices
                DEVICES[device_name] = Device(device_name, address, port, [])
                
        def update_service(self, zeroconf, type, name):
            # This method is required by the interface but we don't need to do anything special
            # when a service is updated. We'll just log it for debugging purposes.
            print(f"Service {name} updated")
    
    zeroconf = Zeroconf()
    listener = MyListener()
    browser = ServiceBrowser(zeroconf, SERVICE_TYPE, listener)
    
    try:
        # Run discovery for 5 seconds
        time.sleep(5)
    finally:
        zeroconf.close()

def start_server(port):
    """Start the Flask server"""
    global PUBLIC_IP, server_thread
    
    try:
        print("1. Getting public IP...")
        PUBLIC_IP = get_public_ip()
        print(f"Public IP: {PUBLIC_IP}")
    except Exception as e:
        print(f"Could not determine public IP: {e}")
        PUBLIC_IP = None
    
    # Start file system watcher in a separate thread with timeout
    def start_file_watcher():
        try:
            print("2. Starting file system watcher...")
            observer.start()
            print("   File system watcher started successfully")
        except Exception as e:
            print(f"   Error starting file system watcher: {e}")
    
    watcher_thread = threading.Thread(target=start_file_watcher, name="FileWatcherThread")
    watcher_thread.daemon = True
    watcher_thread.start()
    
    # Wait for file system watcher to start (with timeout)
    watcher_thread.join(timeout=5)
    if watcher_thread.is_alive():
        print("   Warning: File system watcher is taking too long to start, continuing...")
    
    try:
        print("3. Starting ZeroConf service...")
        start_zeroconf_service(port)
        print("   ZeroConf service started successfully")
    except Exception as e:
        print(f"   Error starting ZeroConf service: {e}")
    
    try:
        print("4. Starting device discovery...")
        discovery_thread = threading.Thread(target=discover_devices, name="DiscoveryThread")
        discovery_thread.daemon = True
        discovery_thread.start()
        print("   Device discovery started in background")
    except Exception as e:
        print(f"   Error starting device discovery: {e}")
    
    # Run Flask in a separate thread
    def run_flask():
        try:
            print("5. Starting Flask server...")
            app.run(host=HOST_IP, port=port, debug=True, use_reloader=False, threaded=True)
        except Exception as e:
            print(f"   Error in Flask server: {e}")
    
    try:
        server_thread = threading.Thread(target=run_flask, name="FlaskThread")
        server_thread.daemon = True
        server_thread.start()
        print("   Flask server started in background")
    except Exception as e:
        print(f"   Error starting Flask server: {e}")
    
    # Print ready message
    try:
        local_ip = get_local_ip()
        print("\n" + "="*50)
        print("   HER ŞEY HAZIR!")
        print("="*50)
        print(f"\nYerel Ağda Erişim: http://{local_ip}:{port}")
        if PUBLIC_IP:
            print(f"Genel İnternet Erişimi: http://{PUBLIC_IP}:{port}")
        print("\nUygulama arka planda çalışmaya devam ediyor...")
        print("Çıkmak için Ctrl+C tuşlarına basın.")
        print("="*50 + "\n")
    except Exception as e:
        print(f"Error displaying ready message: {e}")
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSunucu kapatılıyor...")
        try:
            stop_zeroconf_service()
            observer.stop()
            observer.join()
        except Exception as e:
            print(f"Error during shutdown: {e}")
        print("Sunucu başarıyla kapatıldı.")

def get_public_ip():
    """Get the public IP address of the machine"""
    services = [
        'https://api.ipify.org?format=json',
        'https://ipapi.co/json/',
        'https://ipinfo.io/json'
    ]
    
    for service in services:
        try:
            print(f"Trying to get public IP from {service}")
            response = requests.get(service, timeout=5)
            if response.status_code == 200:
                data = response.json()
                ip = data.get('ip') or data.get('ip')
                if ip:
                    print(f"Successfully got public IP: {ip}")
                    return ip
        except Exception as e:
            print(f"Failed to get IP from {service}: {str(e)}")
            continue
    
    print("Warning: Could not determine public IP. Using 127.0.0.1")
    return None

def check_relay_server(server_url):
    """Check if a relay server is available"""
    try:
        response = requests.get(f"{server_url}/status", timeout=5)
        return response.status_code == 200
    except:
        return False

def register_with_server(server_ip, server_port, device_id, shared_folders=None, is_relay=False):
    """Register this device with the central server or relay server"""
    try:
        # Get public IP if available
        global PUBLIC_IP
        if not PUBLIC_IP:
            PUBLIC_IP = get_public_ip()
            
        # Prepare registration data
        data = {
            'device_id': device_id,
            'local_ip': get_local_ip(),
            'public_ip': PUBLIC_IP,
            'port': 5000,
            'is_relay': is_relay,
            'shared_folders': shared_folders or [SHARED_FOLDER],
            'timestamp': int(time.time())
        }
        
        # If this is a relay registration, add relay-specific info
        if is_relay:
            data['relay_capacity'] = 100  # Max concurrent connections
            data['region'] = 'europe'     # Could be dynamic based on IP
        
        # Send registration request
        base_url = f"http://{server_ip}:{server_port}" if not is_relay else server_ip
        url = f"{base_url}/api/register"
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            print(f"Successfully registered with {'relay' if is_relay else 'server'} {server_ip}:{server_port}")
            
            # If this is a relay server, update our relay server list
            if is_relay:
                update_relay_servers(server_ip, server_port, 'active')
                
            return True
        else:
            print(f"Failed to register: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error registering with server: {e}")
        if is_relay:
            update_relay_servers(server_ip, server_port, 'unavailable')
        return False

def update_relay_servers(server_url, status):
    """Update the status of a relay server"""
    global RELAY_SERVERS
    for server in RELAY_SERVERS:
        if server['url'] == server_url:
            server['status'] = status
            break
    else:
        RELAY_SERVERS.append({'url': server_url, 'status': status})

def list_shared_folders(server_ip, server_port):
    """List all shared folders from the server"""
    import requests
    url = f"http://{server_ip}:{server_port}/devices"
    try:
        response = requests.get(url)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}

def main():
    parser = argparse.ArgumentParser(description='Distributed Storage System')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Start as server')
    server_parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to run the server on')
    
    # Client commands
    client_parser = subparsers.add_parser('client', help='Client commands')
    client_subparsers = client_parser.add_subparsers(dest='client_command', help='Client subcommands')
    
    # Register command
    register_parser = client_subparsers.add_parser('register', help='Register with a server')
    register_parser.add_argument('server_ip', help='Server IP address')
    register_parser.add_argument('--server-port', type=int, default=DEFAULT_PORT, help='Server port')
    register_parser.add_argument('--device-id', required=True, help='Unique device ID')
    register_parser.add_argument('--share', action='append', help='Folders to share (can be used multiple times)')
    
    # List command
    list_parser = client_subparsers.add_parser('list', help='List shared folders')
    list_parser.add_argument('server_ip', help='Server IP address')
    list_parser.add_argument('--server-port', type=int, default=DEFAULT_PORT, help='Server port')
    
    args = parser.parse_args()
    
    if args.command == 'server':
        start_server(args.port)
    elif args.command == 'client':
        if args.client_command == 'register':
            result = register_with_server(
                args.server_ip, 
                args.server_port, 
                args.device_id,
                args.share or []
            )
            print(json.dumps(result, indent=2))
        elif args.client_command == 'list':
            folders = list_shared_folders(args.server_ip, args.server_port)
            print(json.dumps(folders, indent=2))
        else:
            client_parser.print_help()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()