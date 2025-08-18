
import os
import threading
from flask import Blueprint, render_template, request, abort, redirect, url_for, flash
from utils.decorators import login_required
from utils.helpers import get_local_ip

main_bp = Blueprint('main', __name__)

def create_main_routes(file_service, network_service, discovery_service):
    
    @main_bp.route('/')
    @main_bp.route('/browse/')
    @main_bp.route('/browse/<path:subpath>')
    @login_required
    def index(subpath=''):
        # Trigger device discovery in the background
        discovery_service.start_discovery_thread()
        
        # Normalize the subpath
        subpath = subpath.strip('/').replace('\\', '/')
        
        try:
            # List directory contents
            files = file_service.list_directory(subpath)
            
            # Build breadcrumbs
            breadcrumbs = [{'name': 'Ana Dizin', 'path': ''}]
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
                        
        except PermissionError:
            abort(403)
        except FileNotFoundError:
            abort(404)
        except Exception as e:
            print(f"Error listing files: {e}")
            abort(500)
        
        # Get network info
        local_ip = get_local_ip()
        port = request.host.split(':')[-1] if ':' in request.host else '5000'
        
        return render_template('index.html', 
                             files=files, 
                             local_ip=local_ip, 
                             port=port,
                             public_ip=network_service.public_ip or 'Not available',
                             current_path=subpath,
                             breadcrumbs=breadcrumbs)
    
    @main_bp.route('/share', methods=['GET', 'POST'])
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
                # Check quota
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                
                has_space, current_usage = file_service.check_quota(file_size)
                if not has_space:
                    flash(f'Not enough space. Need {file_size} bytes, have {file_service.storage_limit - current_usage}', 'error')
                    return redirect(request.url)
                
                # Save file
                from werkzeug.utils import secure_filename
                filepath = os.path.join(file_service.shared_folder, secure_filename(file.filename))
                file.save(filepath)
                flash('File shared successfully!', 'success')
                
            except Exception as e:
                flash(f'Error sharing file: {str(e)}', 'error')
            
            return redirect(url_for('main.share'))
        
        return render_template('share.html')
    
    return main_bp
