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
from collections import deque
from typing import Dict, List, Any, Optional

# Message storage (in-memory only)
class ChatServer:
    MAX_MESSAGE_LENGTH = 1000  # Prevent b64 encoded images
    MESSAGE_LIFETIME = 240  # 4 minutes in seconds
    RATE_LIMIT_MESSAGES_PER_WINDOW = 12
    RATE_LIMIT_WINDOW_SECONDS = 30
    
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.messages: List[Dict[str, Any]] = []
        self.clients: Dict[socket.socket, str] = {}
        self.client_message_times: Dict[socket.socket, deque[float]] = {}
        self.lock = threading.Lock()
        self.server_socket = None
        self.running = False
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def generate_username(self) -> str:
        """Generate a random username - no user choice allowed"""
        adjectives = ['Swift', 'Silent', 'Dark', 'Ghost', 'Shadow', 'Phantom', 'Cipher', 'Echo']
        nouns = ['Raven', 'Wolf', 'Fox', 'Hawk', 'Lynx', 'Owl', 'Viper', 'Cobra']
        number = secrets.randbelow(9999)
        return f"{secrets.choice(adjectives)}{secrets.choice(nouns)}{number:04d}"
    
    def _cleanup_loop(self):
        """Continuously clean up old messages"""
        while True:
            time.sleep(10)  # Check every 10 seconds
            if not self.running:
                continue
            self._cleanup_old_messages()

    def _active_user_count(self) -> int:
        """Return number of currently connected users."""
        with self.lock:
            return len(self.clients)

    def _build_status_payload(self) -> Dict[str, Any]:
        """Build server status payload sent to clients."""
        return {
            "type": "status",
            "active_users": self._active_user_count(),
            "message_lifetime_seconds": self.MESSAGE_LIFETIME,
            "max_message_length": self.MAX_MESSAGE_LENGTH,
            "rate_limit_messages_per_window": self.RATE_LIMIT_MESSAGES_PER_WINDOW,
            "rate_limit_window_seconds": self.RATE_LIMIT_WINDOW_SECONDS,
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def _send_json(self, client_socket: socket.socket, payload: Dict[str, Any]) -> bool:
        """Send a JSON payload to a specific client socket."""
        try:
            client_socket.send((json.dumps(payload) + "\n").encode("utf-8"))
            return True
        except (OSError, socket.error):
            return False

    def send_error(
        self,
        client_socket: socket.socket,
        code: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a structured protocol error to a client."""
        payload: Dict[str, Any] = {
            "type": "error",
            "code": code,
            "message": message,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if extra:
            payload.update(extra)
        self._send_json(client_socket, payload)

    def _check_rate_limit(self, client_socket: socket.socket) -> tuple[bool, int]:
        """
        Enforce a per-client sliding-window rate limit.

        Returns:
            (allowed, retry_after_seconds)
        """
        now = time.time()
        window_start = now - self.RATE_LIMIT_WINDOW_SECONDS
        with self.lock:
            timestamps = self.client_message_times.setdefault(client_socket, deque())
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()

            if len(timestamps) >= self.RATE_LIMIT_MESSAGES_PER_WINDOW:
                retry_after = max(1, int(self.RATE_LIMIT_WINDOW_SECONDS - (now - timestamps[0])))
                return False, retry_after

            timestamps.append(now)
            return True, 0

    def validate_message_content(
        self, message: Any
    ) -> tuple[bool, str, str, Optional[str]]:
        """
        Validate and sanitize client message payload.

        Returns:
            (ok, error_code, error_message, sanitized_message)
        """
        if not isinstance(message, str):
            return False, "invalid_message_type", "Message must be plain text.", None

        message = message.strip()
        if not message:
            return False, "empty_message", "Message cannot be empty.", None

        if len(message) > self.MAX_MESSAGE_LENGTH:
            return (
                False,
                "message_too_long",
                f"Message too long (max {self.MAX_MESSAGE_LENGTH} chars).",
                None,
            )

        # Roughly reject long dense payloads likely to be b64/binary transfer.
        if len(message) > 500 and message.replace("=", "").isalnum():
            return (
                False,
                "encoded_payload_rejected",
                "Message rejected: encoded/binary-like payloads are not allowed.",
                None,
            )

        sanitized = message.replace("<", "").replace(">", "").replace("&", "")
        return True, "", "", sanitized
    
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
        if not isinstance(message, str):
            return False

        message = message.strip()
        if not message or len(message) > self.MAX_MESSAGE_LENGTH:
            return False
        
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
            self.client_message_times[client_socket] = deque()
        
        try:
            # Send welcome message
            welcome = {
                'type': 'welcome',
                'username': username,
                'message': f'Welcome! You are {username}. Messages burn in 4 minutes.',
                'message_lifetime_seconds': self.MESSAGE_LIFETIME,
                'max_message_length': self.MAX_MESSAGE_LENGTH,
                'rate_limit_messages_per_window': self.RATE_LIMIT_MESSAGES_PER_WINDOW,
                'rate_limit_window_seconds': self.RATE_LIMIT_WINDOW_SECONDS,
            }
            self._send_json(client_socket, welcome)
            
            # Send existing messages
            messages = self.get_messages()
            for msg in messages[-50:]:  # Last 50 messages
                msg_data = {
                    'type': 'message',
                    'username': msg['username'],
                    'message': msg['message'],
                    'timestamp': msg['timestamp'].isoformat()
                }
                self._send_json(client_socket, msg_data)

            # Share status with all clients when membership changes.
            self.broadcast_status()
            
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
                                if msg_obj.get('type') != 'message':
                                    self.send_error(
                                        client_socket,
                                        "unsupported_message_type",
                                        "Unsupported message type. Use type='message'.",
                                    )
                                    continue

                                is_valid, code, error_message, sanitized = self.validate_message_content(
                                    msg_obj.get('message', '')
                                )
                                if not is_valid or sanitized is None:
                                    self.send_error(client_socket, code, error_message)
                                    continue

                                allowed, retry_after = self._check_rate_limit(client_socket)
                                if not allowed:
                                    self.send_error(
                                        client_socket,
                                        "rate_limited",
                                        (
                                            "Message rate limit reached. "
                                            f"Try again in {retry_after} seconds."
                                        ),
                                        extra={"retry_after_seconds": retry_after},
                                    )
                                    continue

                                if self.add_message(username, sanitized):
                                    # Broadcast to all clients
                                    self.broadcast_message(username, sanitized)
                                else:
                                    self.send_error(
                                        client_socket,
                                        "message_rejected",
                                        "Message could not be processed.",
                                    )
                            except json.JSONDecodeError:
                                self.send_error(
                                    client_socket,
                                    "invalid_json",
                                    "Invalid JSON payload.",
                                )
                
                except (OSError, socket.error) as e:
                    break
        
        finally:
            with self.lock:
                if client_socket in self.clients:
                    del self.clients[client_socket]
                if client_socket in self.client_message_times:
                    del self.client_message_times[client_socket]
            try:
                client_socket.close()
            except (OSError, socket.error):
                pass
            self.broadcast_status()
    
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

    def broadcast_status(self):
        """Broadcast current server limits and active user count."""
        status_payload = self._build_status_payload()
        status_json = json.dumps(status_payload) + "\n"

        with self.lock:
            dead_clients = []
            for client_socket in list(self.clients.keys()):
                try:
                    client_socket.send(status_json.encode())
                except (OSError, socket.error):
                    dead_clients.append(client_socket)

            for client in dead_clients:
                if client in self.clients:
                    del self.clients[client]
                if client in self.client_message_times:
                    del self.client_message_times[client]
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
        
        print(f"[*] OpSecChat TUI Server running on {self.host}:{self.port}")
        print(f"[*] Messages burn after {self.MESSAGE_LIFETIME} seconds")
        print(f"[*] Max message length: {self.MAX_MESSAGE_LENGTH} chars")
        print(
            "[*] Rate limit: "
            f"{self.RATE_LIMIT_MESSAGES_PER_WINDOW} messages / {self.RATE_LIMIT_WINDOW_SECONDS} sec per user"
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
            self.client_message_times.clear()
        
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
    server = ChatServer(host=args.host, port=args.port)
    
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
