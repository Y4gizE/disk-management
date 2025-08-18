
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.security import check_password_hash
from utils.decorators import login_required
from flask_wtf.csrf import CSRFProtect
from forms import LoginForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    
    # For GET requests, just render the login page
    if request.method == 'GET':
        return render_template('auth/login.html', form=form)
    
    # Handle POST request
    if not form.validate_on_submit():
        # If form validation fails, re-render the login page with form errors
        return render_template('auth/login.html', form=form)
        
    # If we get here, form is valid
        try:
            from app import app
        except ImportError:
            app = current_app._get_current_object()
            if not app:
                print("CRITICAL: Could not get Flask app instance")
                flash('Sistem hatası: Uygulama başlatılamadı', 'error')
                return render_template('auth/login.html', form=form)
        
        # Log the login attempt
        app.logger.info(f"Login attempt from {request.remote_addr}")
        
        # Get password from form
        password = form.password.data
        
        # Check if password hash exists in config
        if not hasattr(app, 'config') or 'PASSWORD_HASH' not in app.config:
            error_msg = 'PASSWORD_HASH not found in app.config'
            app.logger.error(error_msg)
            flash('Sistem yapılandırma hatası: PASSWORD_HASH bulunamadı', 'error')
            return render_template('auth/login.html', form=form)
        
        # Verify password
        try:
            if check_password_hash(app.config['PASSWORD_HASH'], password):
                session['authenticated'] = True
                session.permanent = True  # Make the session permanent
                next_page = request.args.get('next', '')
                app.logger.info('Kullanıcı başarıyla giriş yaptı')
                return redirect(next_page or url_for('main.index'))
            else:
                app.logger.warning(f'Geçersiz giriş denemesi IP: {request.remote_addr}')
                flash('Geçersiz şifre', 'error')
        except Exception as e:
            error_msg = f'Şifre doğrulanırken hata: {str(e)}'
            app.logger.error(error_msg, exc_info=True)
            flash('Şifre doğrulanırken bir hata oluştu', 'error')
        
        return render_template('auth/login.html')
        
    except Exception as e:
        # This is a last resort error handler
        error_msg = f'Beklenmeyen hata: {str(e)}'
        print(f"CRITICAL ERROR: {error_msg}")
        print("Stack trace:", traceback.format_exc())
        
        # Try to log the error if we have an app reference
        if app and hasattr(app, 'logger'):
            app.logger.critical(error_msg, exc_info=True)
        
        # Provide more detailed error information in debug mode
        error_details = str(e)
        if app and app.debug:
            return f"""
            <h1>500 Internal Server Error</h1>
            <h2>Error Details:</h2>
            <pre>{error_msg}</pre>
            <h3>Traceback:</h3>
            <pre>{traceback.format_exc()}</pre>
            """, 500
            
        flash('Sistem hatası: Lütfen daha sonra tekrar deneyin', 'error')
        return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('auth.login'))
