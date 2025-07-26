import os
import sys
import json
import socket
import argparse
import shutil
import time
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, flash
from flask_cors import CORS
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
SHARED_FOLDER = os.path.join(str(Path.home()), 'Downloads', 'DiskStorage')
STORAGE_LIMIT = 5 * 1024 * 1024 * 1024  # 5GB in bytes

# Ensure shared folder exists
os.makedirs(SHARED_FOLDER, exist_ok=True)

from datetime import datetime

app = Flask(__name__, template_folder='templates')
CORS(app)
app.secret_key = os.urandom(24)  # For flash messages

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

@app.route('/api/download/<path:filename>', methods=['GET'])
def download_file(filename):
    """Download a file from shared storage"""
    filepath = os.path.join(SHARED_FOLDER, filename)
    if not os.path.isfile(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        return send_file(
            filepath,
            as_attachment=True,
            download_name=os.path.basename(filepath)
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

# Web Interface
@app.route('/')
def index():
    """Ana sayfa"""
    devices = [device.to_dict() for device in DEVICES.values()]
    return render_template('index.html', devices=devices)

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

@app.route('/devices', methods=['GET'])
def list_devices():
    return jsonify({
        device_id: device.to_dict() 
        for device_id, device in DEVICES.items()
    })

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
    """Get the local IP address of the machine"""
    try:
        # Try different methods to get local IP
        try:
            # Method 1: Using hostname
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if not local_ip.startswith('127.'):
                return local_ip
        except:
            pass
            
        # Method 2: Using UDP connection
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            if local_ip:
                return local_ip
        except:
            pass
            
        return '0.0.0.0'
    except Exception as e:
        return '0.0.0.0'

def start_server(port):
    """Start the Flask server"""
    print(f"Starting server on http://{get_local_ip()}:{port}")
    app.run(host=HOST_IP, port=port, debug=True, use_reloader=False)

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