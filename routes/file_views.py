import os
import io
import zipfile
import tempfile
import shutil
from flask import Blueprint, render_template, request, send_file, redirect, url_for, flash, abort, jsonify
from werkzeug.utils import secure_filename
from utils.decorators import login_required
from utils.helpers import format_size

file_views_bp = Blueprint('file_views', __name__)

def create_file_view_routes(file_service, archive_service):
    
    @file_views_bp.route('/download/<path:filename>', methods=['GET'])
    @login_required
    def download_file(filename):
        """Download a file or folder from shared storage"""
        filename = filename.strip('/').replace('\\', '/')
        filepath = os.path.normpath(os.path.join(file_service.shared_folder, filename)).replace('\\', '/')
        
        # Security check
        shared_folder_abs = os.path.abspath(file_service.shared_folder).replace('\\', '/')
        filepath_abs = os.path.abspath(filepath).replace('\\', '/')
        
        if not filepath_abs.startswith(shared_folder_abs):
            flash('Geçersiz dosya yolu', 'error')
            return redirect(url_for('main.index'))
        
        try:
            if os.path.isfile(filepath_abs):
                return send_file(
                    filepath_abs,
                    as_attachment=True,
                    download_name=os.path.basename(filepath_abs)
                )
            elif os.path.isdir(filepath_abs):
                # Create zip file in memory
                temp_file = io.BytesIO()
                
                with zipfile.ZipFile(temp_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    base_name = os.path.basename(filepath_abs.rstrip(os.sep))
                    
                    for root, dirs, files in os.walk(filepath_abs):
                        for file in files:
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, os.path.dirname(filepath_abs))
                            zipf.write(file_path, rel_path)
                
                temp_file.seek(0)
                
                return send_file(
                    temp_file,
                    as_attachment=True,
                    download_name=f"{base_name}.zip",
                    mimetype='application/zip'
                )
            else:
                flash('Dosya veya klasör bulunamadı', 'error')
                return redirect(url_for('main.index'))
                
        except Exception as e:
            flash(f'Dosya indirilirken hata oluştu: {str(e)}', 'error')
            return redirect(url_for('main.index'))
    
    @file_views_bp.route('/delete/<path:filename>', methods=['DELETE'])
    @login_required
    def delete_file(filename):
        filename = filename.strip('/').replace('\\', '/')
        filepath = os.path.normpath(os.path.join(file_service.shared_folder, filename)).replace('\\', '/')
        
        try:
            file_service.delete_file_or_folder(filepath)
            return jsonify({'success': True})
        except FileNotFoundError:
            return jsonify({'success': False, 'error': 'Dosya veya klasör bulunamadı'}), 404
        except Exception as e:
            print(f"Error deleting {filepath}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @file_views_bp.route('/view-image/<path:filename>')
    @login_required
    def view_image_route(filename):
        """View an image file in a dedicated viewer."""
        filepath = os.path.join(file_service.shared_folder, filename)
        if not os.path.isfile(filepath):
            abort(404)
        
        # Check if the file is an image
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
        if not any(filename.lower().endswith(ext) for ext in image_extensions):
            abort(400, "Not an image file")
        
        return render_template('image_viewer.html',
                             title=os.path.basename(filename),
                             file_path=filename)
    
    @file_views_bp.route('/view-pdf/<path:filename>')
    @login_required
    def view_pdf_route(filename):
        """View a PDF file in a dedicated viewer."""
        filepath = os.path.join(file_service.shared_folder, filename)
        if not os.path.isfile(filepath):
            abort(404)
        
        if not filename.lower().endswith('.pdf'):
            abort(400, "Not a PDF file")
        
        return render_template('pdf_viewer.html',
                             title=os.path.basename(filename),
                             file_path=filename)
    
    @file_views_bp.route('/view-archive/<path:filename>', defaults={'subpath': ''})
    @file_views_bp.route('/view-archive/<path:filename>/<path:subpath>')
    @login_required
    def view_archive(filename, subpath=''):
        """View the contents of a ZIP or RAR archive."""
        filepath = os.path.join(file_service.shared_folder, filename)
        
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            return render_template('error.html', 
                                error_title="Dosya Bulunamadı",
                                error_message=f"{filename} bulunamadı.",
                                back_url=url_for('main.index')), 404
        
        # Check file extension
        is_rar = filename.lower().endswith('.rar')
        if not (filename.lower().endswith('.zip') or is_rar):
            return render_template('error.html',
                                error_title="Desteklenmeyen Dosya Türü",
                                error_message="Sadece .zip ve .rar dosyaları görüntülenebilir.",
                                back_url=url_for('main.index')), 400
        
        subpath = subpath.strip('/')
        
        try:
            archive_data = archive_service.get_archive_contents(filepath, subpath)
            if not archive_data:
                return render_template('error.html',
                                    error_title="Geçersiz Arşiv",
                                    error_message="Dosya bozuk veya desteklenmeyen bir arşiv formatı.",
                                    back_url=url_for('main.index')), 400
            
            # Calculate parent path for navigation
            parent_path = ''
            has_parent = bool(subpath)
            
            if subpath and '/' in subpath:
                parent_path = subpath.rsplit('/', 1)[0]
            elif subpath:
                parent_path = ''
            
            contents = archive_data.get('contents', [])
            
            # Determine which template to use based on archive type
            template_name = 'rar_viewer.html' if is_rar else 'zip_viewer.html'
            
            return render_template(template_name,
                                title=os.path.basename(filename),
                                archive_name=os.path.basename(filename),
                                file_path=filename,
                                contents=contents,
                                file_count=archive_data.get('file_count', len(contents)),
                                total_size=archive_data.get('total_size', 0),
                                is_rar=is_rar,
                                subpath=subpath,
                                parent_path=parent_path,
                                breadcrumbs=archive_data.get('breadcrumbs', []),
                                has_parent=has_parent,
                                format_size=format_size)
        
        except Exception as e:
            print(f"Error processing archive {filepath}: {str(e)}")
            return render_template('error.html',
                                error_title="Beklenmeyen Hata",
                                error_message=f"Arşiv işlenirken bir hata oluştu: {str(e)}",
                                back_url=url_for('main.index')), 500
    
    @file_views_bp.route('/view/<path:filename>')
    @login_required
    def view_file(filename):
        """View a file in the appropriate viewer based on its type."""
        filepath = os.path.join(file_service.shared_folder, filename)
        if not os.path.isfile(filepath):
            abort(404)
        
        # Check if it's an archive file
        archive_data = archive_service.get_archive_contents(filepath)
        if archive_data:
            return redirect(url_for('file_views.view_archive', filename=filename))
        
        filename_lower = filename.lower()
        
        # Image files
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
        if any(filename_lower.endswith(ext) for ext in image_extensions):
            return redirect(url_for('file_views.view_image_route', filename=filename))
        
        # PDF files
        elif filename_lower.endswith('.pdf'):
            return redirect(url_for('file_views.view_pdf_route', filename=filename))
        
        # Text files
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return render_template('viewer.html', 
                                filename=filename, 
                                content=content)
        except:
            return "Cannot display file content (binary or unsupported encoding)"
    
    return file_views_bp