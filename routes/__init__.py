from .auth import auth_bp
from .main import create_main_routes
from .api import create_api_routes
from .file_views import create_file_view_routes

__all__ = [
    'auth_bp',
    'create_main_routes',
    'create_api_routes', 
    'create_file_view_routes'
]
