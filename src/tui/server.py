"""
OpSecChat TUI Server

A privacy-focused chat server that runs over Tor with a Terminal UI.
All messages are stored in-memory only and burn after 4 minutes.

Features:
- In-memory only (zero disk writes)
- Messages auto-delete after 4 minutes with overwriting
- Randomized usernames (no user choice)
- Text-only (no images, videos, or b64 encoded data)
- Tor hidden service integration
- Optional PGP encryption
"""

import sys
import time
import datetime
import secrets
import threading
import socket
import json
from typing import Dict, List, Any, Optional, Tuple

# Message storage (in-memory only)
class ChatServer:
    MAX_MESSAGE_LENGTH = 1000  # Prevent b64 encoded images
    MESSAGE_LIFETIME = 240  # 4 minutes in seconds
    
    def __init__(
        self,
        host='127.0.0.1',
        port=5555,
        rate_limit_count: int = 30,
        rate_limit_window_seconds: int = 60,
    ):
        self.host = host
        self.port = port
        self.rate_limit_count = max(1, int(rate_limit_count))
        self.rate_limit_window_seconds = max(1, int(rate_limit_window_seconds))
        self.messages: List[Dict[str, Any]] = []
        self.clients: Dict[socket.socket, str] = {}
        self.user_message_timestamps: Dict[str, List[datetime.datetime]] = {}
        self.lock = threading.Lock()
        self.server_socket = None
        self.running = False
        self.cleanup_thread: Optional[threading.Thread] = None
    
    def generate_username(self) -> str:
        """Generate a random username - no user choice allowed"""
        adjectives = ['Swift', 'Silent', 'Dark', 'Ghost', 'Shadow', 'Phantom', 'Cipher', 'Echo']
        nouns = ['Raven', 'Wolf', 'Fox', 'Hawk', 'Lynx', 'Owl', 'Viper', 'Cobra']
        number = secrets.randbelow(9999)
        return f"{secrets.choice(adjectives)}{secrets.choice(nouns)}{number:04d}"
    
    def _cleanup_loop(self):
        """Continuously clean up old messages"""
        while self.running:
            time.sleep(10)  # Check every 10 seconds
            if self.running:
                self._cleanup_old_messages()
    
    def _cleanup_old_messages(self):
        """Remove and overwrite messages older than MESSAGE_LIFETIME"""
        with self.lock:
            now = datetime.datetime.now()
            # Create new list without old messages
            new_messages = []
            
            for msg in self.messages:
                age = (now - msg['timestamp']).total_seconds()
                if age < self.MESSAGE_LIFETIME:
                    new_messages.append(msg)
                else:
                    # Overwrite message data before deletion (security)
                    msg['message'] = 'X' * len(msg['message'])
                    msg['username'] = 'X' * len(msg['username'])
            
            self.messages = new_messages
            self._cleanup_rate_limit_state(now)

    def _cleanup_rate_limit_state(self, now: Optional[datetime.datetime] = None):
        """Prune stale rate-limit entries to bound memory usage."""
        if now is None:
            now = datetime.datetime.now()

        active_usernames = set(self.clients.values())
        cutoff = now - datetime.timedelta(seconds=self.rate_limit_window_seconds)
        users_to_delete = []

        for username, timestamps in self.user_message_timestamps.items():
            filtered = [ts for ts in timestamps if ts > cutoff]
            if filtered and username in active_usernames:
                self.user_message_timestamps[username] = filtered
            else:
                users_to_delete.append(username)

        for username in users_to_delete:
            del self.user_message_timestamps[username]

    def _check_rate_limit(self, username: str) -> Tuple[bool, int]:
        """
        Return (allowed, retry_after_seconds) for a username.

        Retry-after is 0 when allowed.
        """
        with self.lock:
            now = datetime.datetime.now()
            cutoff = now - datetime.timedelta(seconds=self.rate_limit_window_seconds)

            timestamps = self.user_message_timestamps.setdefault(username, [])
            timestamps[:] = [ts for ts in timestamps if ts > cutoff]

            if len(timestamps) >= self.rate_limit_count:
                oldest = timestamps[0]
                elapsed = (now - oldest).total_seconds()
                retry_after = max(1, int(self.rate_limit_window_seconds - elapsed))
                return False, retry_after

            timestamps.append(now)
            return True, 0
    
    def add_message(self, username: str, message: str) -> bool:
        """Add a message to the chat (with validation)"""
        # Validate message
        if not message or len(message) > self.MAX_MESSAGE_LENGTH:
            return False
        
        # Check for potential b64 encoded data (rough heuristic)
        if len(message) > 500 and message.replace('=', '').isalnum():
            return False  # Likely b64 encoded image/video
        
        # Strip any HTML/special chars
        message = message.replace('<', '').replace('>', '').replace('&', '')
        
        with self.lock:
            self.messages.append({
                'username': username,
                'message': message,
                'timestamp': datetime.datetime.now()
            })
        
        return True
    
    def get_messages(self, since: datetime.datetime = None) -> List[Dict[str, Any]]:
        """Get messages (optionally since a specific time)"""
        with self.lock:
            if since is None:
                return self.messages.copy()
            else:
                return [msg for msg in self.messages if msg['timestamp'] > since]
    
    def handle_client(self, client_socket: socket.socket, addr):
        """Handle a client connection"""
        username = self.generate_username()
        
        with self.lock:
            self.clients[client_socket] = username
        
        try:
            # Send welcome message
            welcome = {
                'type': 'welcome',
                'username': username,
                'message': f'Welcome! You are {username}. Messages burn in 4 minutes.'
            }
            client_socket.send((json.dumps(welcome) + '\n').encode())
            
            # Send existing messages
            messages = self.get_messages()
            for msg in messages[-50:]:  # Last 50 messages
                msg_data = {
                    'type': 'message',
                    'username': msg['username'],
                    'message': msg['message'],
                    'timestamp': msg['timestamp'].isoformat()
                }
                client_socket.send((json.dumps(msg_data) + '\n').encode())
            
            # Handle incoming messages
            buffer = ""
            while self.running:
                try:
                    data = client_socket.recv(4096).decode('utf-8')
                    if not data:
                        break
                    
                    buffer += data
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line:
                            try:
                                msg_obj = json.loads(line)
                                if msg_obj.get('type') == 'message':
                                    message = msg_obj.get('message', '')
                                    allowed, retry_after = self._check_rate_limit(username)
                                    if not allowed:
                                        system_msg = {
                                            'type': 'system',
                                            'message': (
                                                f'Rate limit exceeded: max {self.rate_limit_count} '
                                                f'messages per {self.rate_limit_window_seconds}s. '
                                                f'Try again in {retry_after}s.'
                                            )
                                        }
                                        client_socket.send((json.dumps(system_msg) + '\n').encode())
                                        continue

                                    if self.add_message(username, message):
                                        # Broadcast to all clients
                                        self.broadcast_message(username, message)
                                    else:
                                        system_msg = {
                                            'type': 'system',
                                            'message': (
                                                f'Message rejected. Keep it under '
                                                f'{self.MAX_MESSAGE_LENGTH} chars and text-only.'
                                            )
                                        }
                                        client_socket.send((json.dumps(system_msg) + '\n').encode())
                            except json.JSONDecodeError:
                                pass
                
                except (OSError, socket.error) as e:
                    break
        
        finally:
            with self.lock:
                if client_socket in self.clients:
                    departing_user = self.clients.pop(client_socket)
                    self.user_message_timestamps.pop(departing_user, None)
            try:
                client_socket.close()
            except (OSError, socket.error):
                pass
    
    def broadcast_message(self, username: str, message: str):
        """Broadcast a message to all connected clients"""
        msg_data = {
            'type': 'message',
            'username': username,
            'message': message,
            'timestamp': datetime.datetime.now().isoformat()
        }
        msg_json = json.dumps(msg_data) + '\n'
        
        with self.lock:
            dead_clients = []
            for client_socket in list(self.clients.keys()):
                try:
                    client_socket.send(msg_json.encode())
                except (OSError, socket.error):
                    dead_clients.append(client_socket)
            
            # Remove dead clients
            for client in dead_clients:
                if client in self.clients:
                    del self.clients[client]
                try:
                    client.close()
                except (OSError, socket.error):
                    pass
    
    def start(self):
        """Start the chat server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        print(f"[*] OpSecChat TUI Server running on {self.host}:{self.port}")
        print(f"[*] Messages burn after {self.MESSAGE_LIFETIME} seconds")
        print(f"[*] Max message length: {self.MAX_MESSAGE_LENGTH} chars")
        print(
            f"[*] Rate limit: {self.rate_limit_count} messages / "
            f"{self.rate_limit_window_seconds} seconds per user"
        )
        print(f"[*] Press Ctrl+C to stop")
        
        try:
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    client_thread.start()
                except KeyboardInterrupt:
                    break
                except (OSError, socket.error):
                    continue
        finally:
            self.stop()
    
    def stop(self):
        """Stop the chat server"""
        self.running = False
        
        # Close all client connections
        with self.lock:
            for client in list(self.clients.keys()):
                try:
                    client.close()
                except (OSError, socket.error):
                    pass
            self.clients.clear()
            self.user_message_timestamps.clear()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except (OSError, socket.error):
                pass
        
        # Overwrite and clear messages (security)
        with self.lock:
            for msg in self.messages:
                msg['message'] = 'X' * len(msg['message'])
                msg['username'] = 'X' * len(msg['username'])
            self.messages.clear()
        
        print("\n[*] Server stopped. All messages overwritten and cleared.")


def setup_tor_hidden_service(port: int) -> Optional[tuple]:
    """
    Setup Tor hidden service for the chat server
    
    Returns:
        tuple: (hostname, service_id) or None if Tor unavailable
    """
    try:
        from stem.control import Controller
        from stem import SocketError
        
        with Controller.from_port(port=9051) as controller:
            controller.authenticate()
            
            print('[*] Creating ephemeral hidden service, this may take a minute or two')
            result = controller.create_ephemeral_hidden_service(
                {80: port}, await_publication=True
            )
            
            if result.service_id:
                hostname = result.service_id + ".onion"
                print(f"[*] Hidden service created: {hostname}")
                return hostname, result.service_id
            else:
                print("[!] Unable to determine ephemeral service's hostname")
                return None
    
    except ImportError:
        print("[!] stem library not found. Install with: pip install stem")
        print("[*] Running without Tor integration")
        return None
    except SocketError as e:
        print(f"[!] Tor proxy or Control Port not running: {e}")
        print("[*] To use Tor: Start Tor daemon with ControlPort 9051")
        print("[*] Running without Tor integration")
        return None
    except Exception as e:
        print(f"[!] Tor configuration error: {e}")
        print("[*] Running without Tor integration")
        return None


def main():
    """Main entry point for TUI server"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OpSecChat TUI Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (use 0.0.0.0 for all interfaces)')
    parser.add_argument('--port', type=int, default=5555, help='Port to bind to')
    parser.add_argument('--tor', action='store_true', help='Enable Tor hidden service')
    parser.add_argument('--test', action='store_true', help='Test mode (skip Tor even if --tor specified)')
    parser.add_argument(
        '--rate-limit-count',
        type=int,
        default=30,
        help='Max messages per user within the rate-limit window (default: 30)',
    )
    parser.add_argument(
        '--rate-limit-window',
        type=int,
        default=60,
        help='Rate-limit window in seconds (default: 60)',
    )
    args = parser.parse_args()
    
    # Tor integration
    tor_info = None
    if args.tor and not args.test:
        print("[*] Starting with Tor integration...")
        tor_info = setup_tor_hidden_service(args.port)
        if tor_info:
            hostname, service_id = tor_info
            print(f"[*] Share this address: {hostname}:{args.port}")
            print(f"[*] Clients should connect to: {hostname}")
    
    # Create and start server
    server = ChatServer(
        host=args.host,
        port=args.port,
        rate_limit_count=args.rate_limit_count,
        rate_limit_window_seconds=args.rate_limit_window,
    )
    
    print("\n" + "="*60)
    if tor_info:
        print(f"[*] Tor Hidden Service: {tor_info[0]}")
    print(f"[*] Local Server: {args.host}:{args.port}")
    print("="*60 + "\n")
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
    finally:
        server.stop()
        
        # Remove Tor hidden service
        if tor_info:
            try:
                from stem.control import Controller
                with Controller.from_port(port=9051) as controller:
                    controller.authenticate()
                    controller.remove_ephemeral_hidden_service(tor_info[1])
                    print("[*] Tor hidden service removed")
            except Exception as e:
                print(f"[!] Could not remove hidden service: {e}")


if __name__ == '__main__':
    main()
