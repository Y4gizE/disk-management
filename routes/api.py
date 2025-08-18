
import os
import time
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
from utils.decorators import login_required

api_bp = Blueprint('api', __name__, url_prefix='/api')

def create_api_routes(file_service, network_service):
    
    @api_bp.route('/disk_usage', methods=['GET'])
    def get_disk_usage_info():
        """Get current disk usage information"""
        usage = file_service.get_disk_usage()
        return jsonify({
            'used': usage,
            'total': file_service.storage_limit,
            'free': max(0, file_service.storage_limit - usage),
            'usage_percent': (usage / file_service.storage_limit) * 100 if file_service.storage_limit > 0 else 0
        })
    
    @api_bp.route('/upload', methods=['POST'])
    def upload_file():
        """Handle file upload with quota checking"""
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        # Check file size against quota
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        has_space, current_usage = file_service.check_quota(file_size)
        if not has_space:
            return jsonify({
                'error': 'Not enough disk space',
                'current_usage': current_usage,
                'requested': file_size,
                'available': max(0, file_service.storage_limit - current_usage)
            }), 507
        
        # Save the file
        filename = os.path.join(file_service.shared_folder, secure_filename(file.filename))
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
    
    @api_bp.route('/devices', methods=['GET'])
    def list_devices():
        """List all discovered devices"""
        try:
            devices = network_service.get_devices()
            current_time = time.time()
            
            devices_list = [{
                'device_id': device.device_id,
                'ip': device.ip,
                'port': device.port,
                'shared_folders': device.shared_folders,
                'last_seen': device.last_seen,
                'status': 'online' if (current_time - device.last_seen) < 60 else 'offline'
            } for device in devices]
            
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
    
    @api_bp.route('/register', methods=['POST'])
    def register_device():
        data = request.json
        device_id = data.get('device_id')
        ip = request.remote_addr
        port = data.get('port', 5000)
        shared_folders = data.get('shared_folders', [])
        
        if not device_id:
            return jsonify({'error': 'Device ID is required'}), 400
        
        network_service.register_device(device_id, ip, port, shared_folders)
        return jsonify({'status': 'success', 'message': f'Device {device_id} registered'})
    
    return api_bp
