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
import re
from typing import Dict, List, Any, Optional

# Message storage (in-memory only)
class ChatServer:
    MAX_MESSAGE_LENGTH = 1000  # Prevent b64 encoded images
    MESSAGE_LIFETIME = 180  # 3 minutes in seconds
    
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.messages: List[Dict[str, Any]] = []
        self.clients: Dict[socket.socket, str] = {}
        self.client_rooms: Dict[socket.socket, str] = {}
        self.lock = threading.Lock()
        self.server_socket = None
        self.running = False
        self._is_stopped = False
        self.stop_event = threading.Event()
        
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
        while not self.stop_event.is_set():
            # Wait with timeout so shutdown can interrupt quickly.
            self.stop_event.wait(10)
            if self.stop_event.is_set():
                break
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

    def normalize_room_name(self, room_name: str) -> Optional[str]:
        """Validate and normalize a room name."""
        if not isinstance(room_name, str):
            return None
        normalized = room_name.strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]{1,32}", normalized):
            return None
        return normalized

    def get_client_room(self, client_socket: socket.socket) -> str:
        """Get a client's current room, defaulting to lobby."""
        with self.lock:
            return self.client_rooms.get(client_socket, 'lobby')

    def set_client_room(self, client_socket: socket.socket, room_name: str) -> Optional[str]:
        """Set a client's room. Returns normalized room or None if invalid."""
        normalized = self.normalize_room_name(room_name)
        if not normalized:
            return None
        with self.lock:
            self.client_rooms[client_socket] = normalized
        return normalized
    
    def add_message(self, username: str, message: str, room: str = 'lobby') -> bool:
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
                'room': room,
                'username': username,
                'message': message,
                'timestamp': datetime.datetime.now()
            })
        
        return True
    
    def get_messages(self, since: datetime.datetime = None, room: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get messages optionally filtered by timestamp and room."""
        with self.lock:
            filtered = self.messages
            if room is not None:
                filtered = [msg for msg in filtered if msg.get('room', 'lobby') == room]
            if since is None:
                return filtered.copy()
            return [msg for msg in filtered if msg['timestamp'] > since]

    def _send_json(self, client_socket: socket.socket, payload: Dict[str, Any]) -> bool:
        """Send a JSON payload to one client."""
        try:
            client_socket.send((json.dumps(payload) + '\n').encode())
            return True
        except (OSError, socket.error):
            return False

    def send_system_message(self, client_socket: socket.socket, message: str):
        """Send a system message to one client."""
        self._send_json(client_socket, {
            'type': 'system',
            'message': message,
            'timestamp': datetime.datetime.now().isoformat(),
        })

    def join_room(self, client_socket: socket.socket, requested_room: str) -> Optional[Dict[str, str]]:
        """
        Move a client to a room.
        Returns a dict with old/new room names, or None for invalid names.
        """
        new_room = self.normalize_room_name(requested_room)
        if not new_room:
            return None
        with self.lock:
            old_room = self.client_rooms.get(client_socket, 'lobby')
            self.client_rooms[client_socket] = new_room
        return {'old_room': old_room, 'new_room': new_room}
    
    def handle_client(self, client_socket: socket.socket, addr):
        """Handle a client connection"""
        username = self.generate_username()
        
        with self.lock:
            self.clients[client_socket] = username
            self.client_rooms[client_socket] = 'lobby'
        
        try:
            # Send welcome message
            welcome = {
                'type': 'welcome',
                'username': username,
                'room': 'lobby',
                'message': f'Welcome! You are {username}. Messages burn in 3 minutes. Use /join <room> to switch rooms.'
            }
            self._send_json(client_socket, welcome)
            
            # Send existing messages
            current_room = self.get_client_room(client_socket)
            messages = self.get_messages(room=current_room)
            for msg in messages[-50:]:  # Last 50 messages
                msg_data = {
                    'type': 'message',
                    'room': msg.get('room', 'lobby'),
                    'username': msg['username'],
                    'message': msg['message'],
                    'timestamp': msg['timestamp'].isoformat()
                }
                if not self._send_json(client_socket, msg_data):
                    break
            
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
                                msg_type = msg_obj.get('type')
                                if msg_type == 'join_room':
                                    room_change = self.join_room(client_socket, msg_obj.get('room', ''))
                                    if not room_change:
                                        self.send_system_message(
                                            client_socket,
                                            "Invalid room. Use 1-32 chars: a-z, 0-9, _ or -."
                                        )
                                        continue

                                    old_room = room_change['old_room']
                                    new_room = room_change['new_room']
                                    if old_room == new_room:
                                        self.send_system_message(client_socket, f"Already in room '{new_room}'.")
                                        continue

                                    self._send_json(client_socket, {
                                        'type': 'room_joined',
                                        'room': new_room,
                                        'previous_room': old_room,
                                        'message': f"Joined room '{new_room}' (from '{old_room}').",
                                        'timestamp': datetime.datetime.now().isoformat(),
                                    })
                                    recent_messages = self.get_messages(room=new_room)
                                    for old_msg in recent_messages[-50:]:
                                        self._send_json(client_socket, {
                                            'type': 'message',
                                            'room': old_msg.get('room', 'lobby'),
                                            'username': old_msg['username'],
                                            'message': old_msg['message'],
                                            'timestamp': old_msg['timestamp'].isoformat()
                                        })

                                elif msg_type == 'message':
                                    message = msg_obj.get('message', '')
                                    # Backward-compatible text command for older clients.
                                    if isinstance(message, str) and message.lower().startswith('/join '):
                                        room_change = self.join_room(client_socket, message[6:].strip())
                                        if not room_change:
                                            self.send_system_message(
                                                client_socket,
                                                "Invalid room. Use 1-32 chars: a-z, 0-9, _ or -."
                                            )
                                            continue
                                        old_room = room_change['old_room']
                                        new_room = room_change['new_room']
                                        if old_room == new_room:
                                            self.send_system_message(client_socket, f"Already in room '{new_room}'.")
                                            continue
                                        self._send_json(client_socket, {
                                            'type': 'room_joined',
                                            'room': new_room,
                                            'previous_room': old_room,
                                            'message': f"Joined room '{new_room}' (from '{old_room}').",
                                            'timestamp': datetime.datetime.now().isoformat(),
                                        })
                                        recent_messages = self.get_messages(room=new_room)
                                        for old_msg in recent_messages[-50:]:
                                            self._send_json(client_socket, {
                                                'type': 'message',
                                                'room': old_msg.get('room', 'lobby'),
                                                'username': old_msg['username'],
                                                'message': old_msg['message'],
                                                'timestamp': old_msg['timestamp'].isoformat()
                                            })
                                        continue

                                    room = self.get_client_room(client_socket)
                                    if self.add_message(username, message, room=room):
                                        # Broadcast to clients in the same room.
                                        self.broadcast_message(username, message, room=room)
                            except json.JSONDecodeError:
                                self.send_system_message(client_socket, "Ignored malformed JSON message.")
                
                except (OSError, socket.error):
                    break
        
        finally:
            with self.lock:
                if client_socket in self.clients:
                    del self.clients[client_socket]
                if client_socket in self.client_rooms:
                    del self.client_rooms[client_socket]
            try:
                client_socket.close()
            except (OSError, socket.error):
                pass
    
    def broadcast_message(self, username: str, message: str, room: str = 'lobby'):
        """Broadcast a message to clients in one room."""
        msg_data = {
            'type': 'message',
            'room': room,
            'username': username,
            'message': message,
            'timestamp': datetime.datetime.now().isoformat()
        }
        msg_json = json.dumps(msg_data) + '\n'
        
        with self.lock:
            dead_clients = []
            for client_socket in list(self.clients.keys()):
                if self.client_rooms.get(client_socket, 'lobby') != room:
                    continue
                try:
                    client_socket.send(msg_json.encode())
                except (OSError, socket.error):
                    dead_clients.append(client_socket)
            
            # Remove dead clients
            for client in dead_clients:
                if client in self.clients:
                    del self.clients[client]
                if client in self.client_rooms:
                    del self.client_rooms[client]
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
        if self._is_stopped:
            return
        self._is_stopped = True
        self.running = False
        self.stop_event.set()
        
        # Close all client connections
        with self.lock:
            for client in list(self.clients.keys()):
                try:
                    client.close()
                except (OSError, socket.error):
                    pass
            self.clients.clear()
            self.client_rooms.clear()
        
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
