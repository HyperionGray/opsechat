"""
opsechat - Anonymous Chat Server over Tor

Main server file that creates the Flask application and manages the Tor hidden service.
This file has been refactored to use modular blueprints for better code organization.

Original functionality preserved while improving maintainability.
"""

import sys
import os
from stem.control import Controller
from stem import SocketError
import logging

# Import the app factory and utilities
from app_factory import create_app
from utils import id_generator

# Set up logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Create the Flask application
app = create_app()


def main():
    """Main function to start the Tor hidden service and Flask application"""
    # Get Tor control connection parameters from environment
    tor_host = os.environ.get('TOR_CONTROL_HOST', '127.0.0.1')
    
    # Validate and parse port number
    try:
        tor_port = int(os.environ.get('TOR_CONTROL_PORT', '9051'))
        if not (1 <= tor_port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {tor_port}")
    except ValueError as e:
        sys.stderr.write(f'[!] Invalid TOR_CONTROL_PORT value: {e}\n')
        sys.exit(1)
    
    try:
        controller = Controller.from_port(address=tor_host, port=tor_port)
    except SocketError:
        sys.stderr.write(f'[!] Tor proxy or Control Port are not running at {tor_host}:{tor_port}. '
                        f'Try starting the Tor Browser or Tor daemon and ensure the ControlPort is open.\n')
        sys.exit(1)
    
    print('[*] Connecting to tor')
    with controller:
        controller.authenticate()

        # Create ephemeral hidden service where visitors of port 80 get redirected to local
        # port 5000 (this is where Flask runs by default).
        print('[*] Creating ephemeral hidden service, this may take a minute or two')
        result = controller.create_ephemeral_hidden_service({80: 5000}, await_publication=True)

        print("[*] Started a new hidden service with the address of %s.onion" % result.service_id)

        # The hostname is only available when we can read the hidden service
        # directory. This requires us to be running with the same user as tor.

        if not result:
            print("[*] Something went wrong, shutting down")

        if result.service_id:
            app.config["hostname"] = result.service_id
            app.config["path"] = id_generator(size=32)
            app.config["full_path"] = app.config["hostname"] + ".onion" + "/" + app.config["path"]
            print("[*] Your service is available at: %s , press ctrl+c to quit" % app.config["full_path"])
        else:
            print("[*] Unable to determine our ephemeral service's hostname")

        try:
            app.run(host='0.0.0.0', debug=False, threaded=True)
        finally:
            print(" * Shutting down our hidden service")
            controller.remove_ephemeral_hidden_service(result.service_id)


if __name__ == "__main__":
    main()