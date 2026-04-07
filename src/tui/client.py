"""
OpSecChat TUI Client

A privacy-focused chat client with a Terminal UI.
Connects to OpSecChat server for anonymous, encrypted communication.

Features:
- Clean terminal interface using urwid
- Real-time message updates
- Randomized username (server-assigned)
- Text-only interface (no images/video)
- Messages auto-burn after 4 minutes
- Tor/SOCKS proxy support for .onion addresses
"""

import sys
import socket
import json
import threading
import urwid
import socks  # PySocks for SOCKS proxy support


def create_socket_connection(host, port, use_tor=False, tor_port=9050):
    """
    Create a socket connection, optionally through Tor
    
    Args:
        host: Target host (can be .onion)
        port: Target port
        use_tor: Whether to use Tor SOCKS proxy
        tor_port: Tor SOCKS proxy port (default 9050)
    
    Returns:
        socket: Connected socket
    """
    if use_tor or host.endswith('.onion'):
        # Use SOCKS proxy for Tor
        sock = socks.socksocket()
        sock.set_proxy(socks.SOCKS5, "127.0.0.1", tor_port)
        sock.connect((host, port))
        return sock
    else:
        # Direct connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        return sock



class ChatClient:
    def __init__(self, host='127.0.0.1', port=5555, use_tor=False, tor_port=9050):
        self.host = host
        self.port = port
        self.use_tor = use_tor or host.endswith('.onion')
        self.tor_port = tor_port
        self.socket = None
        self.username = "Unknown"
        self.running = False
        self.message_buffer = ""
        self.connection_status = "Disconnected"
        self.user_count = 0
        self.message_count = 0
        self.message_lifetime_seconds = 240
        
        # UI components
        self.messages_walker = urwid.SimpleFocusListWalker([])
        self.messages_box = urwid.ListBox(self.messages_walker)
        self.input_box = urwid.Edit(">>> ", multiline=False)
        
        # Build UI
        self.build_ui()
    
    def build_ui(self):
        """Build the terminal UI"""
        # Header
        self.header_text = urwid.Text(self._build_header_text(), align='center')
        header = urwid.AttrMap(self.header_text, 'header')
        
        # Footer with instructions
        self.footer_text = urwid.Text(self._build_footer_text())
        footer = urwid.AttrMap(self.footer_text, 'footer')
        
        # Messages area
        messages_frame = urwid.LineBox(
            self.messages_box,
            title="Messages"
        )
        
        # Input area
        input_frame = urwid.LineBox(
            urwid.AttrMap(self.input_box, 'input'),
            title="Type your message"
        )
        
        # Main layout
        body = urwid.Pile([
            ('weight', 4, messages_frame),
            ('pack', input_frame)
        ])
        
        self.frame = urwid.Frame(
            body=body,
            header=header,
            footer=footer
        )
        
        # Color scheme
        self.palette = [
            ('header', 'white,bold', 'dark blue'),
            ('footer', 'white', 'dark gray'),
            ('title', 'yellow,bold', 'dark blue'),
            ('info', 'light cyan', 'dark blue'),
            ('warn', 'light red', 'dark blue'),
            ('username', 'light green,bold', 'dark gray'),
            ('input', 'white', 'black'),
            ('my_message', 'light green', 'black'),
            ('other_message', 'light cyan', 'black'),
            ('system_message', 'yellow', 'black'),
            ('timestamp', 'dark gray', 'black'),
        ]

    def _build_header_text(self):
        """Build dynamic header text with live status indicators."""
        lifetime_minutes = max(1, self.message_lifetime_seconds // 60)
        return [
            ('title', 'OpSecChat TUI - Privacy First'),
            ' | ',
            ('info', f'Status: {self.connection_status}'),
            ' | ',
            ('info', f'Users: {self.user_count}'),
            ' | ',
            ('info', f'Messages: {self.message_count}'),
            ' | ',
            ('info', f'Burn: {lifetime_minutes} min'),
            ' | ',
            ('warn', 'Text only - No images/video')
        ]

    def _build_footer_text(self):
        """Build dynamic footer text with user identity."""
        return [
            ('info', 'Enter'),
            ': Send | ',
            ('info', 'Ctrl+C'),
            ': Quit | ',
            ('warn', 'Your username: '),
            ('username', self.username)
        ]
    
    def add_message(self, username, message, is_system=False):
        """Add a message to the display"""
        if is_system:
            msg_widget = urwid.Text(('system_message', f"* {message}"))
        else:
            is_mine = (username == self.username)
            color = 'my_message' if is_mine else 'other_message'
            msg_widget = urwid.Text([
                (color, f"[{username}] "),
                ('', message)
            ])
        
        self.messages_walker.append(msg_widget)
        
        # Auto-scroll to bottom
        self.messages_box.set_focus(len(self.messages_walker) - 1)
        
        # Limit message history (memory management)
        if len(self.messages_walker) > 200:
            self.messages_walker.pop(0)
    
    def connect(self):
        """Connect to the chat server"""
        try:
            self.connection_status = "Connecting"
            self.update_status_header()
            if self.use_tor:
                self.add_message("System", f"Connecting via Tor to {self.host}:{self.port}...", is_system=True)
            else:
                self.add_message("System", f"Connecting to {self.host}:{self.port}...", is_system=True)
            
            self.socket = create_socket_connection(self.host, self.port, self.use_tor, self.tor_port)
            self.running = True
            self.connection_status = "Connected"
            self.update_status_header()
            
            # Start receive thread
            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
            
            return True
        except ImportError as e:
            self.connection_status = "Disconnected"
            self.update_status_header()
            self.add_message("System", f"Missing dependency: {e}. Install with: pip install PySocks", is_system=True)
            return False
        except Exception as e:
            self.connection_status = "Disconnected"
            self.update_status_header()
            self.add_message("System", f"Failed to connect: {e}", is_system=True)
            return False
    
    def receive_messages(self):
        """Receive messages from the server"""
        buffer = ""
        
        while self.running:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    self.add_message("System", "Disconnected from server", is_system=True)
                    self.connection_status = "Disconnected"
                    self.update_status_header()
                    self.running = False
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line:
                        try:
                            msg = json.loads(line)
                            self.handle_server_message(msg)
                        except json.JSONDecodeError:
                            pass
            
            except Exception as e:
                if self.running:
                    self.add_message("System", f"Connection error: {e}", is_system=True)
                self.connection_status = "Disconnected"
                self.update_status_header()
                self.running = False
                break
    
    def handle_server_message(self, msg):
        """Handle a message from the server"""
        msg_type = msg.get('type')
        
        if msg_type == 'welcome':
            self.username = msg.get('username', 'Unknown')
            self.update_footer()
            welcome_msg = msg.get('message', 'Welcome!')
            self.add_message("System", welcome_msg, is_system=True)
        
        elif msg_type == 'message':
            username = msg.get('username', 'Unknown')
            message = msg.get('message', '')
            self.add_message(username, message)

        elif msg_type == 'status':
            self.user_count = msg.get('user_count', self.user_count)
            self.message_count = msg.get('message_count', self.message_count)
            self.message_lifetime_seconds = msg.get(
                'message_lifetime_seconds', self.message_lifetime_seconds
            )
            self.update_status_header()
    
    def update_footer(self):
        """Update the footer with current username"""
        self.footer_text.set_text(self._build_footer_text())

    def update_status_header(self):
        """Update header with live status indicators."""
        self.header_text.set_text(self._build_header_text())
    
    def send_message(self, message):
        """Send a message to the server"""
        if not message or not self.socket:
            return
        
        # Validate message
        if len(message) > 1000:
            self.add_message("System", "Message too long (max 1000 chars)", is_system=True)
            return
        
        try:
            msg_obj = {
                'type': 'message',
                'message': message
            }
            self.socket.send((json.dumps(msg_obj) + '\n').encode())
        except Exception as e:
            self.add_message("System", f"Failed to send: {e}", is_system=True)
    
    def handle_input(self, key):
        """Handle keyboard input"""
        if key == 'enter':
            message = self.input_box.get_edit_text()
            if message.strip():
                self.send_message(message.strip())
                self.input_box.set_edit_text("")
            return
        
        return key
    
    def run(self):
        """Run the TUI client"""
        if not self.connect():
            print("Failed to connect to server. Exiting.")
            sys.exit(1)
        
        # Start urwid main loop
        loop = urwid.MainLoop(
            self.frame,
            palette=self.palette,
            unhandled_input=self.handle_input
        )
        
        try:
            loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        self.connection_status = "Disconnected"
        self.update_status_header()
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except (OSError, socket.error):
                pass


def main():
    """Main entry point for TUI client"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OpSecChat TUI Client')
    parser.add_argument('--host', default='127.0.0.1', help='Server host (can be .onion address)')
    parser.add_argument('--port', type=int, default=5555, help='Server port')
    parser.add_argument('--tor', action='store_true', help='Force use of Tor SOCKS proxy')
    parser.add_argument('--tor-port', type=int, default=9050, help='Tor SOCKS proxy port (default: 9050)')
    args = parser.parse_args()
    
    client = ChatClient(
        host=args.host,
        port=args.port,
        use_tor=args.tor,
        tor_port=args.tor_port
    )
    client.run()


if __name__ == '__main__':
    main()
