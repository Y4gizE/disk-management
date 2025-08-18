#!/usr/bin/env python3
"""
Main entry point for the Disk Management application.
"""
import os
import sys
import argparse
import signal
import logging
from app import create_app

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Disk Management Application')
    parser.add_argument('--port', type=int, default=5000,
                      help='Port to run the server on (default: 5000)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                      help='Host to bind the server to (default: 0.0.0.0)')
    parser.add_argument('--debug', action='store_true',
                      help='Run in debug mode')
    parser.add_argument('--no-browser', action='store_true',
                      help='Do not open browser automatically')
    return parser.parse_args()

def setup_logging(debug=False):
    """Configure logging for the application."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('disk_management.log')
        ]
    )

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    print('\nShutting down...')
    sys.exit(0)

def main():
    """Main application entry point."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up logging
    setup_logging(debug=args.debug)
    logger = logging.getLogger(__name__)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create and configure the Flask application
        app = create_app()
        
        # Print server info
        print("\n" + "=" * 50)
        print(f"Disk Management Application")
        print("=" * 50)
        print(f"Shared folder: {app.config['SHARED_FOLDER']}")
        print(f"Running on: http://{args.host}:{args.port}")
        print("=" * 50 + "\n")
        
        # Run the application
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
        
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
