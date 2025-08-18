"""
Decorators for the application.
"""
from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify
import logging

# Configure logging
logger = logging.getLogger(__name__)

def login_required(f):
    """Ensure user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Ensure user has admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin', False):
            flash('Administrator privileges required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def handle_errors(f):
    """Handle common errors in routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            flash('The requested resource was not found.', 'error')
            return redirect(url_for('main.index'))
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            flash('You do not have permission to access this resource.', 'error')
            return redirect(url_for('main.index'))
        except Exception as e:
            logger.exception(f"Unexpected error in {f.__name__}: {e}")
            flash('An unexpected error occurred. Please try again later.', 'error')
            return redirect(url_for('main.index'))
    return decorated_function

def json_response(f):
    """Convert return value to JSON response."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], int):
                response, status_code = result
                return jsonify({
                    'status': 'success' if status_code < 400 else 'error',
                    'data': response if status_code < 400 else None,
                    'error': response if status_code >= 400 else None,
                    'code': status_code
                }), status_code
            return jsonify({'status': 'success', 'data': result})
        except Exception as e:
            logger.exception(f"Error in JSON response: {e}")
            return jsonify({
                'status': 'error',
                'error': str(e),
                'code': 500
            }), 500
    return decorated_function
