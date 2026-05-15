#!/usr/bin/env python3
"""
OpSecChat - Simple Chat Room Creator

This script provides a simple CLI interface for creating and hosting
secure, ephemeral chat rooms.

Usage:
    python chat-room.py                    # Create a new room
    python chat-room.py --tor              # Create room with Tor hidden service
    python chat-room.py --help             # Show help
"""

import sys
import argparse
from app_factory import create_app
from tor_transport import (
    get_hidden_service_target,
    resolve_tor_control_endpoint,
    tor_ingress_required,
)
from utils import id_generator


def main():
    """Main entry point for chat room creation"""
    parser = argparse.ArgumentParser(
        prog='python bin/chat-room.py',
        description='OpSecChat - Create secure, ephemeral chat rooms',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Create room on localhost
  %(prog)s --tor              # Create room as Tor hidden service
  %(prog)s --port 8080        # Use custom port

Security Features:
  - Messages disappear after 3 minutes
  - In-memory only (no disk storage)
  - Memory overwriting on deletion
  - Randomized usernames with color distinction
  - Closed-roster OpenPGP room bootstrap
  - Text-only (no media)
        """
    )
    
    parser.add_argument(
        '--tor',
        action='store_true',
        help='Create room as Tor hidden service (requires Tor daemon)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to run server on (default: 5000)'
    )
    
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1, use 0.0.0.0 for all interfaces)'
    )
    
    args = parser.parse_args()

    if tor_ingress_required() and not args.tor:
        print("[*] OPSECHAT_REQUIRE_TOR=1 detected; forcing Tor hidden service mode")
        args.tor = True
    
    # Create Flask app
    app = create_app()
    
    # Generate random path for security
    path = id_generator(size=32)
    app.config['path'] = path
    
    if args.tor:
        try:
            from stem.control import Controller
            from stem import SocketError
            
            print('[*] Connecting to Tor...')
            print('[*] Creating ephemeral hidden service, this may take a minute or two')
            
            control_host, control_port = resolve_tor_control_endpoint()
            with Controller.from_port(address=control_host, port=control_port) as controller:
                controller.authenticate()
                
                hs_target = get_hidden_service_target(default_port=args.port)
                result = controller.create_ephemeral_hidden_service(
                    {80: hs_target}, await_publication=True
                )
                
                if result.service_id:
                    hostname = result.service_id + ".onion"
                    app.config['hostname'] = result.service_id
                    app.config['full_path'] = f"{hostname}/chat"
                    
                    print(f'\n{"="*60}')
                    print(f'[tor] OpSecChat hidden service created')
                    print(f'{"="*60}')
                    print(f'\n[console] Operator Console: http://{hostname}/')
                    print(f'[chat]    Chat Rooms:        http://{hostname}/chat')
                    if app.config.get("OPSECHAT_ENABLE_LEGACY_CHAT"):
                        print(f'[legacy]  Legacy Chat:        http://{hostname}/{path}')
                    print(f'\n[!] Share these URLs only with trusted contacts')
                    print(f'[!] Messages auto-delete after 3 minutes')
                    print(f'[!] Closed-roster OpenPGP rooms require explicit roster bootstrap before the first message')
                    print(f'\n{"="*60}')
                    print('\nPress Ctrl+C to stop the server\n')
                    
                    try:
                        app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)
                    finally:
                        print("\n[*] Shutting down hidden service...")
                        try:
                            with Controller.from_port(address=control_host, port=control_port) as ctrl:
                                ctrl.authenticate()
                                ctrl.remove_ephemeral_hidden_service(result.service_id)
                        except Exception as e:
                            print(f"Warning: Could not cleanly remove hidden service: {e}")
                else:
                    print("[!] Unable to determine ephemeral service's hostname")
                    sys.exit(1)
                    
        except ImportError:
            print("[!] Error: 'stem' library not found")
            print("Install with: pip install stem")
            sys.exit(1)
        except SocketError as e:
            print(f"[!] Tor proxy or Control Port not running: {e}")
            print("Try starting the Tor Browser or Tor daemon:")
            print("  - Ensure the configured Tor control endpoint is reachable")
            print("  - Default: tor --ControlPort 9051 --CookieAuthentication 1")
            sys.exit(1)
        except Exception as e:
            print(f"[!] Error setting up Tor: {e}")
            sys.exit(1)
    else:
        # Local mode
        app.config['hostname'] = f"{args.host}:{args.port}"
        app.config['full_path'] = f"http://{args.host}:{args.port}/chat"
        
        print(f'\n{"="*60}')
        print(f'[local] OpSecChat server started')
        print(f'{"="*60}')
        print(f'\n[console] Operator Console: http://{args.host}:{args.port}/')
        print(f'[chat]    Chat Rooms:        http://{args.host}:{args.port}/chat')
        if app.config.get("OPSECHAT_ENABLE_LEGACY_CHAT"):
            print(f'[legacy]  Legacy Chat:        http://{args.host}:{args.port}/{path}')
        print(f'\n[!] For maximum security, use --tor flag')
        print(f'[!] Messages auto-delete after 3 minutes')
        print(f'[!] Closed-roster OpenPGP rooms require explicit roster bootstrap before the first message')
        print(f'\n{"="*60}')
        print('\nPress Ctrl+C to stop the server\n')
        
        try:
            app.run(host=args.host, port=args.port, debug=False, threaded=True)
        except KeyboardInterrupt:
            print("\n[*] Server stopped")
        except Exception as e:
            print(f"\n[!] Error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
