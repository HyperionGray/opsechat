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
from typing import Dict, List, Any, Optional

# Message storage (in-memory only)
class ChatServer:
    MAX_MESSAGE_LENGTH = 1000  # Prevent b64 encoded images
    MESSAGE_LIFETIME = 240  # 4 minutes in seconds
    RATE_LIMIT_MESSAGES = 8
    RATE_LIMIT_WINDOW_SECONDS = 10

    def __init__(
        self,
        host='127.0.0.1',
        port=5555,
        rate_limit_messages: Optional[int] = None,
        rate_limit_window_seconds: Optional[int] = None,
    ):
        self.host = host
        self.port = port
        self.messages: List[Dict[str, Any]] = []
        self.clients: Dict[socket.socket, str] = {}
        self.lock = threading.Lock()
        self.server_socket = None
        self.running = False

        self.rate_limit_messages = (
            rate_limit_messages
            if rate_limit_messages is not None
            else self.RATE_LIMIT_MESSAGES
        )
        self.rate_limit_window_seconds = (
            rate_limit_window_seconds
            if rate_limit_window_seconds is not None
            else self.RATE_LIMIT_WINDOW_SECONDS
        )
        self.rate_limit_messages = max(1, int(self.rate_limit_messages))
        self.rate_limit_window_seconds = max(1, int(self.rate_limit_window_seconds))

        # Per-user message timestamps for rate limiting and feedback for rejected messages.
        self.user_message_timestamps: Dict[str, List[float]] = {}
        self.rejection_reasons: Dict[str, str] = {}

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
    
    def add_message(self, username: str, message: str) -> bool:
        """Add a message to the chat (with validation)"""
        # Validate message
        if not message:
            with self.lock:
                self.rejection_reasons[username] = "Message cannot be empty."
            return False

        if len(message) > self.MAX_MESSAGE_LENGTH:
            with self.lock:
                self.rejection_reasons[username] = (
                    f"Message too long (max {self.MAX_MESSAGE_LENGTH} chars)."
                )
            return False

        # Check for potential b64 encoded data (rough heuristic)
        if len(message) > 500 and message.replace('=', '').isalnum():
            with self.lock:
                self.rejection_reasons[username] = (
                    "Message looks like encoded/binary payload and was blocked."
                )
            return False  # Likely b64 encoded image/video

        # Strip any HTML/special chars
        message = message.replace('<', '').replace('>', '').replace('&', '')
        if not message.strip():
            with self.lock:
                self.rejection_reasons[username] = "Message became empty after sanitization."
            return False

        with self.lock:
            now_ts = time.time()
            cutoff = now_ts - self.rate_limit_window_seconds

            timestamps = self.user_message_timestamps.setdefault(username, [])
            timestamps[:] = [ts for ts in timestamps if ts >= cutoff]

            if len(timestamps) >= self.rate_limit_messages:
                self.rejection_reasons[username] = (
                    f"Rate limit exceeded: max {self.rate_limit_messages} messages per "
                    f"{self.rate_limit_window_seconds} seconds."
                )
                return False

            timestamps.append(now_ts)
            self.messages.append({
                'username': username,
                'message': message,
                'timestamp': datetime.datetime.now()
            })
            self.rejection_reasons.pop(username, None)
        
        return True

    def get_rejection_reason(self, username: str) -> Optional[str]:
        """Return the last rejection reason for a user."""
        with self.lock:
            return self.rejection_reasons.get(username)

    def send_system_message(self, client_socket: socket.socket, message: str, level: str = 'warning'):
        """Send a system message to a specific client."""
        payload = {
            'type': 'system',
            'level': level,
            'message': message,
            'timestamp': datetime.datetime.now().isoformat(),
        }
        try:
            client_socket.send((json.dumps(payload) + '\n').encode())
        except (OSError, socket.error):
            pass
    
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
                'message': (
                    f'Welcome! You are {username}. Messages burn in 4 minutes. '
                    f'Rate limit: {self.rate_limit_messages}/{self.rate_limit_window_seconds}s.'
                )
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
                                    if self.add_message(username, message):
                                        # Broadcast to all clients
                                        self.broadcast_message(username, message)
                                    else:
                                        reason = self.get_rejection_reason(username)
                                        if reason:
                                            self.send_system_message(client_socket, reason)
                            except json.JSONDecodeError:
                                pass
                
                except (OSError, socket.error) as e:
                    break
        
        finally:
            with self.lock:
                if client_socket in self.clients:
                    del self.clients[client_socket]
                self.user_message_timestamps.pop(username, None)
                self.rejection_reasons.pop(username, None)
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
            "[*] Message rate limit: "
            f"{self.rate_limit_messages} per {self.rate_limit_window_seconds} seconds"
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
            self.user_message_timestamps.clear()
            self.rejection_reasons.clear()

        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=1)
        
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
        '--rate-limit-messages',
        type=int,
        default=ChatServer.RATE_LIMIT_MESSAGES,
        help='Max messages allowed per rate-limit window (default: 8)',
    )
    parser.add_argument(
        '--rate-limit-window',
        type=int,
        default=ChatServer.RATE_LIMIT_WINDOW_SECONDS,
        help='Rate-limit window in seconds (default: 10)',
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
        rate_limit_messages=args.rate_limit_messages,
        rate_limit_window_seconds=args.rate_limit_window,
    )
    
    print("\n" + "="*60)
    if tor_info:
        print(f"🧅 Tor Hidden Service: {tor_info[0]}")
    print(f"📡 Local Server: {args.host}:{args.port}")
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
