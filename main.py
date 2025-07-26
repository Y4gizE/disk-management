import os
import sys
import json
import socket
import argparse
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from pathlib import Path
import threading
import time
import os

from datetime import datetime

app = Flask(__name__, template_folder='templates')
CORS(app)
app.secret_key = os.urandom(24)  # For flash messages

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
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        return '127.0.0.1'

def start_server(port):
    """Start the Flask server"""
    print(f"Starting server on http://{get_local_ip()}:{port}")
    app.run(host=HOST_IP, port=port, debug=True, use_reloader=False)

def register_with_server(server_ip, server_port, device_id, shared_folders=None):
    """Register this device with the central server"""
    if shared_folders is None:
        shared_folders = []
    
    import requests
    url = f"http://{server_ip}:{server_port}/register"
    try:
        response = requests.post(url, json={
            'device_id': device_id,
            'port': DEFAULT_PORT,
            'shared_folders': shared_folders
        })
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}

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