#!/usr/bin/env python3
"""
Refactored opsechat server entry point

This is a significantly simplified version of the original runserver.py,
using the app factory pattern and modular blueprint architecture.
All route handlers have been moved to appropriate blueprint modules.
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
            
            # Check if hidden service already exists
            hidden_services = controller.get_hidden_service_conf()
            if not hidden_services:
                # Create new hidden service
                response = controller.create_ephemeral_hidden_service(
                    {80: 5000}, await_publication=True
                )
                hostname = response.service_id + ".onion"
                print(f"Hidden service created: {hostname}")
                return hostname
            else:
                # Use existing hidden service
                for service in hidden_services:
                    if hasattr(service, 'hostname'):
                        return service.hostname
                        
    except SocketError as e:
        print(f"Warning: Could not connect to Tor control port: {e}")
        print("Running without Tor hidden service")
        return "localhost"
    except Exception as e:
        print(f"Warning: Tor configuration error: {e}")
        return "localhost"


def main():
    """Main application entry point"""
    # Create Flask application using factory pattern
    app = create_app()
    
    # Generate random path for security
    path = id_generator(size=16)
    hostname = setup_tor_configuration()
    
    # Configure application
    app.config['path'] = path
    app.config['hostname'] = hostname
    
    print(f"Starting opsechat server...")
    print(f"Access URL: http://{hostname}/{path}")
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Test mode: Running on localhost:5001")
        app.run(host='127.0.0.1', port=5001, debug=False)
    else:
        # Production mode
        app.run(host='127.0.0.1', port=5000, debug=False)


if __name__ == "__main__":
    main()