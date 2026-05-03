#!/usr/bin/env python3
"""
Refactored opsechat server entry point

This is a significantly simplified version of the original runserver.py,
using the app factory pattern and modular blueprint architecture.
All route handlers have been moved to appropriate blueprint modules.

Original file was 906 lines, refactored to ~70 lines for better maintainability.
"""

import os
import signal
import sys
import logging
import threading
import time
from stem.control import Controller
from stem import ControllerError, SocketError
from stem.connection import AuthenticationFailure
from app_factory import create_app
from tor_transport import (
    resolve_tor_control_endpoint,
    tor_ingress_required,
)
from utils import id_generator

# Configure logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


def _get_positive_float_env(name, default, minimum):
    """Read a float env var and clamp it to a safe minimum."""
    raw_value = os.environ.get(name, str(default))
    try:
        return max(float(raw_value), minimum)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a float, got {raw_value!r}") from exc


def setup_tor_configuration():
    """Setup Tor hidden service configuration"""
    timeout_seconds = _get_positive_float_env(
        "OPSECHAT_TOR_STARTUP_TIMEOUT",
        30,
        1.0,
    )
    retry_delay_seconds = _get_positive_float_env(
        "OPSECHAT_TOR_RETRY_DELAY",
        1,
        0.1,
    )
    deadline = time.monotonic() + timeout_seconds
    last_error = None

    while time.monotonic() < deadline:
        try:
            control_host, control_port = resolve_tor_control_endpoint()
            with Controller.from_port(address=control_host, port=control_port) as controller:
                controller.authenticate()

                # Create ephemeral hidden service.
                # await_publication=True blocks until the HS descriptors are published
                # to HSDir nodes (~60-120 s).  Flask is already serving at this point
                # (Tor setup runs in a background thread), so the health-check endpoint
                # remains reachable throughout.
                print('[*] Creating ephemeral hidden service, this may take a minute or two')
                result = controller.create_ephemeral_hidden_service(
                    {80: 5000}, await_publication=True
                )

                if result.service_id:
                    hostname = result.service_id + ".onion"
                    print(f"[*] Started a new hidden service with the address of {hostname}")
                    return hostname, result.service_id

                print("[*] Unable to determine our ephemeral service's hostname")
                return "localhost", None
        except (AuthenticationFailure, ControllerError, OSError, SocketError) as e:
            last_error = e
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(retry_delay_seconds, remaining))

    if isinstance(last_error, SocketError):
        print(f"[!] Tor proxy or Control Port are not running: {last_error}")
        print("Try starting the Tor Browser or Tor daemon and ensure the ControlPort is open.")
    else:
        print(f"Warning: Tor configuration error: {last_error}")

    if tor_ingress_required():
        raise RuntimeError("Tor ingress is required but the hidden service could not be created") from last_error
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
    
    # Set provisional config so Flask can answer health checks before Tor is ready.
    app.config['path'] = path
    app.config['hostname'] = "localhost"
    app.config['full_path'] = f"localhost/{path}"

    # Mutable containers shared with the background thread.
    _service_id = [None]

    def _tor_setup_worker():
        """Run Tor hidden-service setup in the background.

        Flask starts (and the /health endpoint becomes reachable) before this
        function is called, so container health checks always succeed even when
        Tor publication takes 60-120 s.
        """
        try:
            hostname, service_id = setup_tor_configuration()
        except RuntimeError as exc:
            print(f"[!] {exc}")
            # Tor is required but unavailable – stop the whole process.
            # sys.exit() only exits the current thread; os.kill(SIGTERM) signals
            # the main thread, which triggers Flask's graceful shutdown handler.
            os.kill(os.getpid(), signal.SIGTERM)
            return

        _service_id[0] = service_id
        app.config['hostname'] = (
            hostname.replace('.onion', '') if hostname.endswith('.onion') else hostname
        )
        app.config['full_path'] = f"{hostname}/{path}"
        print(f"[*] Your service is available at: http://{app.config['full_path']}")

    # Start Tor setup in the background so Flask can bind immediately.
    tor_thread = threading.Thread(target=_tor_setup_worker, daemon=True, name="tor-setup")
    tor_thread.start()

    print("Press Ctrl+C to quit")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    finally:
        service_id = _service_id[0]
        if service_id:
            print(" * Shutting down our hidden service")
            try:
                control_host, control_port = resolve_tor_control_endpoint()
                with Controller.from_port(address=control_host, port=control_port) as controller:
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
