
import os
import sys
import time
import threading
import argparse
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask import Flask
from flask_cors import CORS
from watchdog.observers import Observer

# Import our modules
from config import Config
from models.device import Device
from services.file_service import FileService
from services.network_service import NetworkService
from services.archive_service import ArchiveService
from services.rar_service import RarService
from services.discovery_service import DiscoveryService
from utils.helpers import get_local_ip, get_public_ip
from utils.decorators import login_required

# Import route modules
from routes.auth import auth_bp
from routes.main import create_main_routes
from routes.api import create_api_routes
from routes.file_views import create_file_view_routes

# Global variables
observer = None
PUBLIC_IP = None

class FileChangeHandler:
    """Handle file system change events"""
    def __init__(self, network_service):
        self.network_service = network_service
    
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
        rel_path = os.path.relpath(file_path, Config.SHARED_FOLDER)
        devices = self.network_service.get_devices()
        
        for device in devices:
            if device.device_id != os.uname().nodename:
                try:
                    # In a real app, send notification to peer's API
                    pass
                except Exception as e:
                    print(f"Error notifying {device.device_id}: {str(e)}")

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__, template_folder='templates')
    CORS(app)
    
    # Add a simple route to check if the app is running
    @app.route('/health')
    def health_check():
        return 'OK', 200
        
    # Add a debug route to show configuration
    @app.route('/debug')
    def debug_info():
        if not app.debug and not app.testing:
            return 'Debug information is only available in debug mode', 403
            
        import platform
        import sys
        from flask import jsonify
        
        config_info = {
            'python_version': sys.version,
            'flask_version': '1.1.2',  # Hardcoded as we can't import flask.__version__ directly
            'platform': platform.platform(),
            'app_config': {k: v for k, v in app.config.items() if not k.startswith('SECRET')},
            'services': {
                'file_watcher': 'Running' if 'observer' in globals() and observer else 'Not running',
                'zeroconf': 'Running' if hasattr(app, 'network_service') else 'Not running',
                'discovery': 'Running' if hasattr(app, 'discovery_service') and hasattr(app.discovery_service, 'running') and app.discovery_service.running else 'Not running'
            }
        }
        return jsonify(config_info)
    
    # Configure app
    app.secret_key = Config.SECRET_KEY
    app.config['PASSWORD_HASH'] = generate_password_hash(Config.DEFAULT_PASSWORD)
    
    # Enable CSRF protection
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_SECRET_KEY'] = Config.SECRET_KEY
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour in seconds
    
    # Initialize Flask-WTF CSRF protection
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)
    
    # Enable detailed error logging
    import logging
    from logging.handlers import RotatingFileHandler
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Configure file handler
    file_handler = RotatingFileHandler('logs/disk_management.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.DEBUG)
    
    # Add handlers to app logger
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.DEBUG)
    app.logger.info('Disk Management startup')
    
    # Log configuration values (except secrets)
    app.logger.debug(f"Configuration: HOST_IP={Config.HOST_IP}")
    app.logger.debug(f"Configuration: PORT={getattr(Config, 'PORT', 'Not set')}")
    app.logger.debug(f"Configuration: SHARED_FOLDER={Config.SHARED_FOLDER}")
    app.logger.debug(f"Configuration: DEBUG_MODE={getattr(Config, 'DEBUG_MODE', 'Not set')}")
    
    # Register error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.error(f'404 Error: {error}')
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'500 Error: {error}', exc_info=True)
        return render_template('errors/500.html'), 500
        
    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f'Unhandled Exception: {e}', exc_info=True)
        return render_template('errors/500.html'), 500
    
    # Initialize services
    file_service = FileService(Config.SHARED_FOLDER)
    
    # Initialize network service with default values
    service_name = f"disk-management-{os.getpid()}"  # Unique service name
    service_port = Config.PORT if hasattr(Config, 'PORT') else 5000
    network_service = NetworkService(
        service_name=service_name,
        service_port=service_port,
        service_properties={
            'version': '1.0',
            'path': '/',
            'description': 'Disk Management Service'
        }
    )
    
    rar_service = RarService()
    archive_service = ArchiveService(rar_service)
    discovery_service = DiscoveryService(network_service)
    
    # Custom Jinja2 filters
    @app.template_filter('datetime')
    def format_datetime(timestamp, format='%d.%m.%Y %H:%M:%S'):
        if timestamp is None:
            return "-"
        return datetime.fromtimestamp(timestamp).strftime(format)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(create_main_routes(file_service, network_service, discovery_service))
    app.register_blueprint(create_api_routes(file_service, network_service))
    app.register_blueprint(create_file_view_routes(file_service, archive_service))
    
    # Store services in app context for access from other modules
    app.file_service = file_service
    app.network_service = network_service
    app.archive_service = archive_service
    app.discovery_service = discovery_service
    
    return app

def start_file_watcher(network_service):
    """Start file system watcher"""
    global observer
    
    try:
        print("Starting file system watcher...")
        event_handler = FileChangeHandler(network_service)
        observer = Observer()
        observer.schedule(event_handler, Config.SHARED_FOLDER, recursive=True)
        observer.start()
        print("File system watcher started successfully")
    except Exception as e:
        print(f"Error starting file system watcher: {e}")

def start_server(port):
    """Start the Flask server with all services"""
    global PUBLIC_IP
    
    # Configure Flask to show detailed error pages
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '1'
    
    app = create_app()
    app.config['DEBUG'] = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    try:
        print("1. Getting public IP...")
        PUBLIC_IP = get_public_ip()
        app.network_service.public_ip = PUBLIC_IP
        print(f"Public IP: {PUBLIC_IP}")
    except Exception as e:
        print(f"Could not determine public IP: {e}")
        PUBLIC_IP = None
    
    # Start file system watcher
    watcher_thread = threading.Thread(
        target=start_file_watcher, 
        args=(app.network_service,), 
        daemon=True
    )
    watcher_thread.start()
    
    try:
        print("2. Registering ZeroConf service...")
        if app.network_service.register_service():
            print("ZeroConf service registered successfully")
        else:
            print("Failed to register ZeroConf service")
    except Exception as e:
        print(f"Error starting ZeroConf service: {e}")
    
    # Start device discovery
    try:
        print("3. Starting device discovery...")
        if hasattr(app.discovery_service, 'start_discovery_thread'):
            if app.discovery_service.start_discovery_thread():
                print("Device discovery started successfully")
            else:
                print("Failed to start device discovery")
        else:
            print("DiscoveryService does not have start_discovery_thread method")
    except Exception as e:
        print(f"Error starting device discovery: {e}")
    
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
    
    try:
        print("4. Starting Flask server...")
        app.run(host=Config.HOST_IP, port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nSunucu kapatılıyor...")
        shutdown_server(app.network_service)
    except Exception as e:
        print(f"Error in Flask server: {e}")
        shutdown_server(app.network_service)

def shutdown_server(network_service):
    """Gracefully shutdown the server"""
    try:
        network_service.stop_zeroconf_service()
        if observer:
            observer.stop()
            observer.join()
        print("Sunucu başarıyla kapatıldı.")
    except Exception as e:
        print(f"Error during shutdown: {e}")

def register_with_server(server_ip, server_port, device_id, shared_folders=None, is_relay=False):
    """Register this device with a server"""
    import requests
    
    try:
        data = {
            'device_id': device_id,
            'local_ip': get_local_ip(),
            'public_ip': get_public_ip(),
            'port': Config.DEFAULT_PORT,
            'is_relay': is_relay,
            'shared_folders': shared_folders or [Config.SHARED_FOLDER],
            'timestamp': int(time.time())
        }
        
        if is_relay:
            data['relay_capacity'] = 100
            data['region'] = 'europe'
        
        base_url = f"http://{server_ip}:{server_port}" if not is_relay else server_ip
        url = f"{base_url}/api/register"
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            print(f"Successfully registered with {'relay' if is_relay else 'server'} {server_ip}:{server_port}")
            return True
        else:
            print(f"Failed to register: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error registering with server: {e}")
        return False

def list_shared_folders(server_ip, server_port):
    """List all shared folders from the server"""
    import requests
    
    url = f"http://{server_ip}:{server_port}/api/devices"
    try:
        response = requests.get(url)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Distributed Storage System')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Start as server')
    server_parser.add_argument('--port', type=int, default=Config.DEFAULT_PORT, 
                              help='Port to run the server on')
    
    # Client commands
    client_parser = subparsers.add_parser('client', help='Client commands')
    client_subparsers = client_parser.add_subparsers(dest='client_command', 
                                                     help='Client subcommands')
    
    # Register command
    register_parser = client_subparsers.add_parser('register', help='Register with a server')
    register_parser.add_argument('server_ip', help='Server IP address')
    register_parser.add_argument('--server-port', type=int, default=Config.DEFAULT_PORT, 
                                help='Server port')
    register_parser.add_argument('--device-id', required=True, help='Unique device ID')
    register_parser.add_argument('--share', action='append', 
                                help='Folders to share (can be used multiple times)')
    
    # List command
    list_parser = client_subparsers.add_parser('list', help='List shared folders')
    list_parser.add_argument('server_ip', help='Server IP address')
    list_parser.add_argument('--server-port', type=int, default=Config.DEFAULT_PORT, 
                            help='Server port')
    
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
            import json
            print(json.dumps({'success': result}, indent=2))
        elif args.client_command == 'list':
            folders = list_shared_folders(args.server_ip, args.server_port)
            import json
            print(json.dumps(folders, indent=2))
        else:
            client_parser.print_help()
    else:
        # Default to server mode if no command specified
        start_server(Config.DEFAULT_PORT)

if __name__ == '__main__':
    main()
