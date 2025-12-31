#!/usr/bin/env python3
"""
Refactored opsechat server entry point

This is a significantly simplified version of the original runserver.py,
using the app factory pattern and modular blueprint architecture.
All route handlers have been moved to appropriate blueprint modules.

Original file was 906 lines, refactored to ~70 lines for better maintainability.
"""

import sys
import os
import logging
from stem.control import Controller
from stem import SocketError
from app_factory import create_app
from utils import id_generator

# Configure logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


def setup_tor_configuration():
    """Setup Tor hidden service configuration"""
    try:
        with Controller.from_port(port=9051) as controller:
            controller.authenticate()
            
            # Create ephemeral hidden service
            print('[*] Creating ephemeral hidden service, this may take a minute or two')
            result = controller.create_ephemeral_hidden_service(
                {80: 5000}, await_publication=True
            )
            
            if result.service_id:
                hostname = result.service_id + ".onion"
                print(f"[*] Started a new hidden service with the address of {hostname}")
                return hostname, result.service_id
            else:
                print("[*] Unable to determine our ephemeral service's hostname")
                return "localhost", None
                
    except SocketError as e:
        print(f"[!] Tor proxy or Control Port are not running: {e}")
        print("Try starting the Tor Browser or Tor daemon and ensure the ControlPort is open.")
        return "localhost", None
    except Exception as e:
        print(f"Warning: Tor configuration error: {e}")
        return "localhost", None


def main():
    """Main application entry point"""
    # Create Flask application using factory pattern
    app = create_app()
    
    # Generate random path for security
    path = id_generator(size=32)
    
    # Check for test mode
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Test mode: Running on localhost:5001")
        app.config['path'] = path
        app.config['hostname'] = "localhost"
        app.config['full_path'] = f"localhost:5001/{path}"
        print(f"[*] Your service is available at: http://{app.config['full_path']}")
        app.run(host='127.0.0.1', port=5001, debug=False)
        return
    
    # Production mode with Tor
    hostname, service_id = setup_tor_configuration()
    
    # Configure application
    app.config['path'] = path
    app.config['hostname'] = hostname.replace('.onion', '') if hostname.endswith('.onion') else hostname
    app.config['full_path'] = f"{hostname}/{path}"
    
    print(f"[*] Your service is available at: http://{app.config['full_path']}")
    print("Press Ctrl+C to quit")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    finally:
        if service_id:
            print(" * Shutting down our hidden service")
            try:
                with Controller.from_port(port=9051) as controller:
                    controller.authenticate()
                    controller.remove_ephemeral_hidden_service(service_id)
            except Exception as e:
                print(f"Warning: Could not cleanly remove hidden service: {e}")


# Create a global app instance for testing
app = create_app()

# Import utility functions for backward compatibility with tests
from utils import id_generator, check_older_than, process_chat

if __name__ == "__main__":
    main()