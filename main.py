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
import time
import subprocess
import magic
import argparse
import shutil
import subprocess
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session, abort, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.serving import run_simple
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import psutil
import requests
try:
    import netifaces
    NETIFACES_AVAILABLE = True
except ImportError:
    NETIFACES_AVAILABLE = False
    print("Warning: netifaces not available. Some network features may be limited.")

# RAR Processor configuration
RAR_PROCESSOR_ENABLED = False
RAR_PROCESSOR_URL = "http://localhost:5001"
RAR_PROCESSOR_CONTAINER_NAME = "rar-processor"

def check_rar_processor():
    """Check if the RAR processor service is running and start it if needed."""
    global RAR_PROCESSOR_ENABLED
    try:
        # Check if the container is already running
        result = subprocess.run(
            ["docker", "inspect", "--format='{{.State.Running}}'", RAR_PROCESSOR_CONTAINER_NAME],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and 'true' in result.stdout:
            RAR_PROCESSOR_ENABLED = True
            print("RAR processor container is already running")
            return True
            
        # If not running, try to start it
        print("Starting RAR processor container...")
        subprocess.run([
            "docker", "start", RAR_PROCESSOR_CONTAINER_NAME
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for the container to start
        time.sleep(2)
        RAR_PROCESSOR_ENABLED = True
        print("RAR processor container started successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to start RAR processor container. Please run 'start_rar_processor.bat' first.")
        print(f"Error: {e.stderr}" if e.stderr else f"Error: {e}")
        RAR_PROCESSOR_ENABLED = False
        return False

def get_archive_contents_docker(archive_path):
    """Get archive contents using the Docker-based RAR processor."""
    try:
        # Convert to relative path for the container
        rel_path = os.path.relpath(archive_path, SHARED_FOLDER)
        container_path = f"/shared/{rel_path.replace(os.sep, '/')}"
        
        response = requests.post(
            f"{RAR_PROCESSOR_URL}/list",
            json={"file_path": container_path},
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
        return None

from zeroconf import ServiceInfo, Zeroconf, IPVersion
from typing import List, Dict, Any, Optional, Union
import io
import tempfile
from pathlib import Path

# Load environment variables
load_dotenv()

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
    """Download a file from shared storage"""
    # Normalize the filename and handle Windows paths
    filename = filename.strip('/').replace('\\', '/')
    filepath = os.path.normpath(os.path.join(SHARED_FOLDER, filename)).replace('\\', '/')
    
    # Security check to prevent directory traversal
    shared_folder_abs = os.path.abspath(SHARED_FOLDER).replace('\\', '/')
    filepath_abs = os.path.abspath(filepath).replace('\\', '/')
    
    if not filepath_abs.startswith(shared_folder_abs) or not os.path.isfile(filepath_abs):
        flash('Dosya bulunamadı', 'error')
        return redirect(url_for('index'))
    
    try:
        return send_file(
            filepath_abs,
            as_attachment=True,
            download_name=os.path.basename(filepath_abs)
        )
    except Exception as e:
        flash(f'Dosya indirilirken hata oluştu: {str(e)}', 'error')
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
    return datetime.fromtimestamp(timestamp).strftime(format)

# Global variables
DEVICES = {}
SHARED_FOLDERS = {}
HOST_IP = '0.0.0.0'
PUBLIC_IP = None
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

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if check_password_hash(app.config['PASSWORD_HASH'], password):
            session['authenticated'] = True
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid password', 'error')
    return '''
        <form method="post">
            <h2>Enter Password</h2>
            <input type="password" name="password" required>
            <button type="submit">Login</button>
        </form>
    '''

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
        entries = []
        total_size = 0
        file_count = 0
        is_rar = False
        
        # Normalize subpath (remove leading/trailing slashes)
        subpath = subpath.strip('/')
        
        # Check if it's a RAR file
        if archive_path.lower().endswith('.rar'):
            is_rar = True
            # Try using Docker RAR processor first
            if check_rar_processor():
                result = get_archive_contents_docker(archive_path)
                if result:
                    return result
                print("Falling back to local RAR processing")
            
            # Fallback to local processing
            try:
                if not os.access(archive_path, os.R_OK):
                    print(f"No read permissions for RAR file: {archive_path}")
                    return None
                    
                file_size = os.path.getsize(archive_path)
                if file_size == 0:
                    print(f"Empty RAR file: {archive_path}")
                    return None
                
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
                            # Skip directories (we'll handle them from the paths)
                            if item.isdir():
                                continue
                                
                            # Get relative path and check if it's in the current subpath
                            rel_path = item.filename.replace('\\', '/').rstrip('/')
                            if subpath and not (rel_path == subpath or rel_path.startswith(f"{subpath}/")):
                                continue
                                
                            # Calculate the path relative to the current subpath
                            display_path = rel_path[len(subpath)+1:] if subpath else rel_path
                            path_parts = display_path.split('/')
                            
                            # Add directory entries for the path
                            current_path = []
                            for part in path_parts[:-1]:  # All but the last part are directories
                                current_path.append(part)
                                dir_path = '/'.join(current_path)
                                
                                # Check if we've already added this directory
                                if not any(e['path'] == dir_path for e in entries):
                                    entries.append({
                                        'name': part,
                                        'path': f"{subpath}/{dir_path}" if subpath else dir_path,
                                        'size': 0,
                                        'date': datetime.fromtimestamp(item.mtime) if hasattr(item, 'mtime') else None,
                                        'is_dir': True
                                    })
                            
                            # Add the file entry
                            if path_parts[-1]:  # Skip empty filenames (shouldn't happen)
                                total_size += item.file_size
                                file_count += 1
                                
                                entries.append({
                                    'name': path_parts[-1],
                                    'path': rel_path,
                                    'size': item.file_size,
                                    'date': datetime.fromtimestamp(item.mtime) if hasattr(item, 'mtime') else None,
                                    'is_dir': False
                                })
                                
                        except Exception as e:
                            print(f"Error processing RAR entry {item.filename}: {str(e)}")
                            continue
                            
            except (rarfile.BadRarFile, rarfile.NotRarFile, rarfile.RarCannotExec) as e:
                print(f"Error processing RAR file {archive_path}: {str(e)}")
                return None
            except Exception as e:
                print(f"Unexpected error processing RAR file {archive_path}: {str(e)}")
                import traceback
                traceback.print_exc()
                return None
        
        # Handle ZIP files
        elif archive_path.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    for item in zip_ref.infolist():
                        try:
                            # Skip directories (we'll handle them from the paths)
                            if item.filename.endswith('/'):
                                continue
                                
                            # Get relative path and check if it's in the current subpath
                            rel_path = item.filename.replace('\\', '/').rstrip('/')
                            if subpath and not (rel_path == subpath or rel_path.startswith(f"{subpath}/")):
                                continue
                                
                            # Calculate the path relative to the current subpath
                            display_path = rel_path[len(subpath)+1:] if subpath else rel_path
                            path_parts = display_path.split('/')
                            
                            # Add directory entries for the path
                            current_path = []
                            for part in path_parts[:-1]:  # All but the last part are directories
                                current_path.append(part)
                                dir_path = '/'.join(current_path)
                                
                                # Check if we've already added this directory
                                if not any(e['path'] == dir_path for e in entries):
                                    entries.append({
                                        'name': part,
                                        'path': f"{subpath}/{dir_path}" if subpath else dir_path,
                                        'size': 0,
                                        'date': datetime(*item.date_time) if hasattr(item, 'date_time') else None,
                                        'is_dir': True
                                    })
                            
                            # Add the file entry
                            if path_parts[-1]:  # Skip empty filenames (shouldn't happen)
                                total_size += item.file_size
                                file_count += 1
                                
                                entries.append({
                                    'name': path_parts[-1],
                                    'path': rel_path,
                                    'size': item.file_size,
                                    'date': datetime(*item.date_time) if hasattr(item, 'date_time') else None,
                                    'is_dir': False
                                })
                                
                        except Exception as e:
                            print(f"Error processing ZIP entry {item.filename}: {str(e)}")
                            continue
                            
            except zipfile.BadZipFile as e:
                print(f"Bad ZIP file {archive_path}: {str(e)}")
                return None
            except Exception as e:
                print(f"Error reading ZIP file {archive_path}: {str(e)}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print(f"Unsupported archive format: {archive_path}")
            return None
        
        # Build the directory structure
        dir_structure = build_directory_structure(entries)
        
        # Get the current directory contents
        current_contents = []
        if subpath:
            # Find the current directory in the structure
            parts = subpath.split('/')
            current = dir_structure
            for part in parts:
                found = False
                for child in current.get('children', []):
                    if child['name'] == part and child['is_dir']:
                        current = child
                        found = True
                        break
                if not found:
                    # Subpath not found, return empty contents
                    current = None
                    break
            
            if current:
                current_contents = current.get('children', [])
        else:
            current_contents = dir_structure.get('children', [])
        
        # Prepare breadcrumbs
        breadcrumbs = [{'name': os.path.basename(archive_path), 'path': ''}]
        if subpath:
            path_parts = []
            for part in subpath.split('/'):
                if part:
                    path_parts.append(part)
                    breadcrumbs.append({
                        'name': part,
                        'path': '/'.join(path_parts)
                    })
        
        return {
            'name': os.path.basename(archive_path),
            'path': archive_path,
            'size': total_size,
            'file_count': file_count,
            'contents': sorted(current_contents, key=lambda x: (not x['is_dir'], x['name'].lower())),
            'is_archive': True,
            'is_rar': is_rar,
            'subpath': subpath,
            'breadcrumbs': breadcrumbs,
            'has_parent': bool(subpath)
        }
        
    except (zipfile.BadZipFile, rarfile.BadRarFile, rarfile.NotRarFile, Exception) as e:
        print(f"Error reading archive {archive_path}: {str(e)}")
        return None

def get_file_info(file_path, base_path=None):
    if base_path is None:
        base_path = SHARED_FOLDER
    
    try:
        # Make sure both paths are absolute and normalized
        file_path_abs = os.path.abspath(file_path).replace('\\', '/')
        base_path_abs = os.path.abspath(base_path).replace('\\', '/')
        
        # Get the relative path from the shared folder
        rel_path = os.path.relpath(file_path_abs, SHARED_FOLDER).replace('\\', '/')
        
        # If we're at the root, make sure relative_path is empty
        if rel_path == '.' or file_path_abs == SHARED_FOLDER.replace('\\', '/'):
            rel_path = ''
        
        # For directories, make sure the path ends with a slash
        is_dir = os.path.isdir(file_path_abs)
        if is_dir and rel_path and not rel_path.endswith('/'):
            rel_path += '/'
        
        # Get the name of the file/directory
        name = os.path.basename(file_path_abs)
        
        # Get size information
        if is_dir:
            print(f"Calculating size for folder: {file_path_abs}")
            size_bytes = get_folder_size(file_path_abs)
            formatted_size = format_size(size_bytes)
            raw_size = size_bytes
            print(f"Folder size for {name}: {formatted_size}")
        else:
            try:
                size_bytes = os.path.getsize(file_path_abs)
                formatted_size = format_size(size_bytes)
                raw_size = size_bytes
                print(f"File size for {name}: {formatted_size}")
            except (OSError, PermissionError) as e:
                print(f"Error getting size for {file_path_abs}: {e}")
                size_bytes = 0
                formatted_size = "0 B"
                raw_size = 0
        
        file_info = {
            'name': name,
            'path': file_path_abs,
            'relative_path': rel_path,
            'size': raw_size,
            'formatted_size': formatted_size,
            'modified': os.path.getmtime(file_path_abs),
            'is_dir': is_dir
        }
        
        print(f"File info for {name}: {file_info}")
        return file_info
        
    except Exception as e:
        print(f"Error in get_file_info for {file_path}: {e}")
        # Return minimal info to prevent template errors
        return {
            'name': os.path.basename(file_path),
            'path': file_path,
            'relative_path': '',
            'size': 0,
            'formatted_size': '0 B',
            'modified': 0,
            'is_dir': False
        }

# Web Interface
@app.route('/')
@app.route('/browse/')
@app.route('/browse/<path:subpath>')
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
    filepath = os.path.join(SHARED_FOLDER, filename)
    
    # Check if file exists
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return render_template('error.html', 
                            error_title="Dosya Bulunamadı",
                            error_message=f"{filename} bulunamadı.",
                            back_url=url_for('index')), 404
    
    # Check if it's a file
    if not os.path.isfile(filepath):
        print(f"Not a file: {filepath}")
        return render_template('error.html',
                            error_title="Geçersiz Dosya",
                            error_message=f"{filename} geçerli bir dosya değil.",
                            back_url=url_for('index')), 400
    
    # Check file extension
    if not (filename.lower().endswith('.zip') or filename.lower().endswith('.rar')):
        print(f"Unsupported file type: {filepath}")
        return render_template('error.html',
                            error_title="Desteklenmeyen Dosya Türü",
                            error_message=f"Sadece .zip ve .rar dosyaları görüntülenebilir.",
                            back_url=url_for('index')), 400
    
    # Normalize subpath (remove leading/trailing slashes)
    subpath = subpath.strip('/')
    
    # Get archive contents for the specified subpath
    try:
        archive_data = get_archive_contents(filepath, subpath)
        if not archive_data:
            print(f"Unsupported or corrupted archive: {filepath}")
            return render_template('error.html',
                                error_title="Geçersiz Arşiv",
                                error_message=f"Dosya bozuk veya desteklenmeyen bir arşiv formatı.",
                                back_url=url_for('index')), 400
        
        # If we have a subpath and no contents, it might be a file - try to extract and view it
        if subpath and not archive_data['contents']:
            try:
                # Check if this is a file in the archive
                with zipfile.ZipFile(filepath, 'r') if filename.lower().endswith('.zip') else rarfile.RarFile(filepath, 'r') as archive:
                    try:
                        # Try to get info for the file
                        file_info = archive.getinfo(subpath)
                        if not file_info.is_dir():
                            # Extract the file to a temporary location and serve it
                            temp_dir = tempfile.mkdtemp()
                            temp_path = os.path.join(temp_dir, os.path.basename(subpath))
                            
                            with archive.open(file_info) as source, open(temp_path, 'wb') as target:
                                shutil.copyfileobj(source, target)
                            
                            # Determine the appropriate viewer based on file extension
                            ext = os.path.splitext(subpath)[1].lower()
                            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                                return redirect(url_for('view_image_route', filename=os.path.basename(temp_path), temp=1))
                            elif ext == '.pdf':
                                return redirect(url_for('view_pdf_route', filename=os.path.basename(temp_path), temp=1))
                            else:
                                # For other file types, trigger a download
                                return send_file(temp_path, as_attachment=True)
                    except (KeyError, rarfile.BadRarFile):
                        # File not found in archive
                        pass
            except Exception as e:
                print(f"Error extracting file from archive: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Add parent directory link if we're in a subdirectory
        parent_path = ''
        if subpath:
            parent_parts = subpath.split('/')[:-1]
            if parent_parts:
                parent_path = '/'.join(parent_parts)
        
        return render_template('archive_viewer.html',
                            title=archive_data['name'],
                            archive_name=archive_data['name'],
                            file_path=filename,
                            contents=archive_data['contents'],
                            file_count=archive_data['file_count'],
                            total_size=archive_data['size'],
                            is_rar=archive_data.get('is_rar', False),
                            subpath=subpath,
                            parent_path=parent_path,
                            breadcrumbs=archive_data.get('breadcrumbs', []),
                            has_parent=bool(subpath),
                            format_size=format_size)
    
    except rarfile.BadRarFile as e:
        print(f"Bad RAR file: {filepath} - {str(e)}")
        return render_template('error.html',
                            error_title="Bozuk Arşiv Dosyası",
                            error_message="Arşiv dosyası bozuk veya hasarlı görünüyor.",
                            back_url=url_for('index')), 400
    
    except rarfile.NotRarFile as e:
        print(f"Not a RAR file: {filepath}")
        return render_template('error.html',
                            error_title="Geçersiz RAR Dosyası",
                            error_message="Bu bir RAR dosyası değil veya bozuk olabilir.",
                            back_url=url_for('index')), 400
    
    except rarfile.RarCannotExec as e:
        print(f"RAR executable not found: {str(e)}")
        return render_template('error.html',
                            error_title="Eksik Bağımlılık",
                            error_message="RAR dosyalarını açmak için sisteminizde unrar kurulu olmalıdır.",
                            back_url=url_for('index')), 500
    
    except Exception as e:
        print(f"Unexpected error processing {filepath}: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('error.html',
                            error_title="Beklenmeyen Hata",
                            error_message=f"Arşiv işlenirken bir hata oluştu: {str(e)}",
                            back_url=url_for('index')), 500

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
    global HOST_IP, zeroconf
    HOST_IP = get_local_ip()
    
    # Start ZeroConf service in a separate thread
    zeroconf_thread = threading.Thread(target=start_zeroconf_service, args=(port,))
    zeroconf_thread.daemon = True
    zeroconf_thread.start()
    
    # Start device discovery in a separate thread
    discovery_thread = threading.Thread(target=discover_devices)
    discovery_thread.daemon = True
    discovery_thread.start()
    
    # Start Flask server
    app.run(host=HOST_IP, port=port, debug=True, use_reloader=False, threaded=True)

def get_public_ip():
    """Get the public IP address of the machine"""
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        if response.status_code == 200:
            return response.json().get('ip')
    except:
        pass
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