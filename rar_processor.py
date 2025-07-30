import os
import json
import rarfile
import logging
import traceback
from flask import Flask, request, jsonify
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure RAR file to use the system unrar
rarfile.UNRAR_TOOL = 'unrar'

def get_rar_contents(rar_path):
    """Get contents of a RAR file."""
    logger.info(f"Attempting to read RAR file: {rar_path}")
    
    # Check if file exists and is accessible
    if not os.path.exists(rar_path):
        logger.error(f"RAR file not found: {rar_path}")
        return {
            'success': False,
            'error': 'File not found',
            'path': rar_path
        }
        
    if not os.path.isfile(rar_path):
        logger.error(f"Not a file: {rar_path}")
        return {
            'success': False,
            'error': 'Not a file',
            'path': rar_path
        }
    
    try:
        # Try to get file size for logging
        file_size = os.path.getsize(rar_path)
        logger.info(f"RAR file size: {file_size} bytes")
        
        contents = []
        total_size = 0
        
        with rarfile.RarFile(rar_path, 'r') as rar_ref:
            # Check if RAR is password protected
            if rar_ref.needs_password():
                logger.error("Password-protected RAR files are not supported")
                return {
                    'success': False,
                    'error': 'Password-protected RAR files are not supported',
                    'path': rar_path
                }
                
            file_list = rar_ref.namelist()
            logger.info(f"Found {len(file_list)} entries in RAR file")
            
            if not file_list:
                logger.warning("RAR file is empty")
                return {
                    'success': True,
                    'name': os.path.basename(rar_path),
                    'path': rar_path,
                    'size': 0,
                    'file_count': 0,
                    'contents': [],
                    'is_rar': True
                }
            
            for item in rar_ref.infolist():
                try:
                    name = os.path.basename(item.filename)
                    if not name:  # Skip directory entries
                        continue
                        
                    file_size = item.file_size if not item.isdir() else 0
                    if not item.isdir():
                        total_size += file_size
                    
                    contents.append({
                        'name': name,
                        'size': file_size,
                        'date': item.mtime if hasattr(item, 'mtime') else None,
                        'is_dir': item.isdir()
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing RAR entry {item.filename}: {str(e)}")
                    logger.error(traceback.format_exc())
                    continue
    
        return {
            'success': True,
            'name': os.path.basename(rar_path),
            'path': rar_path,
            'size': total_size,
            'file_count': len(contents),
            'contents': sorted(contents, key=lambda x: (not x['is_dir'], x['name'].lower())),
            'is_rar': True
        }
        
    except rarfile.BadRarFile as e:
        logger.error(f"Bad RAR file: {str(e)}")
        return {
            'success': False,
            'error': 'Bad RAR file',
            'details': str(e),
            'path': rar_path
        }
    except rarfile.NotRarFile as e:
        logger.error(f"Not a RAR file: {str(e)}")
        return {
            'success': False,
            'error': 'Not a RAR file',
            'details': str(e),
            'path': rar_path
        }
    except rarfile.RarCannotExec as e:
        logger.error(f"RAR executable not found: {str(e)}")
        return {
            'success': False,
            'error': 'RAR executable not found',
            'details': 'Make sure unrar is installed in the container',
            'path': rar_path
        }
    except Exception as e:
        logger.error(f"Error processing RAR file: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': 'Error processing RAR file',
            'details': str(e),
            'path': rar_path
        }

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'ok'}), 200

@app.route('/list', methods=['POST'])
def list_archive():
    """List contents of a RAR file."""
    logger.info("Received request to list archive contents")
    
    try:
        # Log request data
        logger.info(f"Request data: {request.data}")
        
        data = request.get_json()
        if not data or 'file_path' not in data:
            logger.error("No file path provided in request")
            return jsonify({
                'success': False,
                'error': 'No file path provided',
                'details': 'The file_path parameter is required'
            }), 400
        
        file_path = data['file_path']
        logger.info(f"Processing file: {file_path}")
        
        # Get the result from the RAR processor
        result = get_rar_contents(file_path)
        
        # If we got a result with success=False, return it as an error
        if not result.get('success', True):
            logger.error(f"Error processing RAR file: {result.get('error', 'Unknown error')}")
            return jsonify(result), 400
            
        return jsonify(result)
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e),
            'traceback': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
