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
        self.server_status = {
            "message_lifetime_seconds": 240,
            "max_message_length": 1000,
            "rate_limit_messages_per_window": None,
            "rate_limit_window_seconds": None,
            "active_users": None,
        }
        
        # UI components
        self.messages_walker = urwid.SimpleFocusListWalker([])
        self.messages_box = urwid.ListBox(self.messages_walker)
        self.input_box = urwid.Edit(">>> ", multiline=False)
        
        # Build UI
        self.build_ui()
    
    def build_ui(self):
        """Build the terminal UI"""
        # Header
        header = urwid.AttrMap(
            urwid.Text([
                ('title', 'OpSecChat TUI - Privacy First'),
                ' | ',
                ('info', self._burn_window_label()),
                ' | ',
                ('warn', 'Text only - No images/video')
            ], align='center'),
            'header'
        )
        
        # Footer with instructions
        footer_text = [
            ('info', 'Enter'),
            ': Send | ',
            ('info', 'Ctrl+C'),
            ': Quit | ',
            ('warn', 'Your username: '),
            ('username', self.username)
        ]
        footer = urwid.AttrMap(urwid.Text(footer_text), 'footer')
        
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

    def _burn_window_label(self):
        """Return burn window label for header/footer."""
        burn_seconds = self.server_status.get("message_lifetime_seconds") or 240
        burn_minutes = burn_seconds // 60
        if burn_seconds % 60 == 0:
            return f"Messages burn in {burn_minutes} min"
        return f"Messages burn in {burn_seconds} sec"

    def _rate_limit_label(self):
        """Return human-readable rate limit label."""
        limit = self.server_status.get("rate_limit_messages_per_window")
        window = self.server_status.get("rate_limit_window_seconds")
        if isinstance(limit, int) and isinstance(window, int):
            return f"Rate: {limit}/{window}s"
        return "Rate: n/a"

    def _user_count_label(self):
        """Return connected user count label."""
        active_users = self.server_status.get("active_users")
        if isinstance(active_users, int):
            return f"Users: {active_users}"
        return "Users: ?"

    def _build_footer(self):
        """Build footer widget with current dynamic status."""
        footer_text = [
            ('info', 'Enter'),
            ': Send | ',
            ('info', 'Ctrl+C'),
            ': Quit | ',
            ('info', self._user_count_label()),
            ' | ',
            ('info', self._rate_limit_label()),
            ' | ',
            ('warn', 'Your username: '),
            ('username', self.username)
        ]
        return urwid.AttrMap(urwid.Text(footer_text), 'footer')

    def _build_header(self):
        """Build header widget with current burn policy."""
        header_text = [
            ('title', 'OpSecChat TUI - Privacy First'),
            ' | ',
            ('info', self._burn_window_label()),
            ' | ',
            ('warn', 'Text only - No images/video')
        ]
        return urwid.AttrMap(urwid.Text(header_text, align='center'), 'header')
    
    def connect(self):
        """Connect to the chat server"""
        try:
            if self.use_tor:
                self.add_message("System", f"Connecting via Tor to {self.host}:{self.port}...", is_system=True)
            else:
                self.add_message("System", f"Connecting to {self.host}:{self.port}...", is_system=True)
            
            self.socket = create_socket_connection(self.host, self.port, self.use_tor, self.tor_port)
            self.running = True
            
            # Start receive thread
            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
            
            return True
        except ImportError as e:
            self.add_message("System", f"Missing dependency: {e}. Install with: pip install PySocks", is_system=True)
            return False
        except Exception as e:
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
                self.running = False
                break
    
    def handle_server_message(self, msg):
        """Handle a message from the server"""
        msg_type = msg.get('type')
        
        if msg_type == 'welcome':
            self.username = msg.get('username', 'Unknown')
            self.server_status["message_lifetime_seconds"] = msg.get(
                "message_lifetime_seconds",
                self.server_status["message_lifetime_seconds"],
            )
            self.server_status["max_message_length"] = msg.get(
                "max_message_length",
                self.server_status["max_message_length"],
            )
            self.server_status["rate_limit_messages_per_window"] = msg.get(
                "rate_limit_messages_per_window",
                self.server_status["rate_limit_messages_per_window"],
            )
            self.server_status["rate_limit_window_seconds"] = msg.get(
                "rate_limit_window_seconds",
                self.server_status["rate_limit_window_seconds"],
            )
            self.update_footer()
            welcome_msg = msg.get('message', 'Welcome!')
            self.add_message("System", welcome_msg, is_system=True)
        
        elif msg_type == 'message':
            username = msg.get('username', 'Unknown')
            message = msg.get('message', '')
            self.add_message(username, message)
        
        elif msg_type == 'status':
            self.server_status["active_users"] = msg.get("active_users")
            self.server_status["message_lifetime_seconds"] = msg.get(
                "message_lifetime_seconds",
                self.server_status["message_lifetime_seconds"],
            )
            self.server_status["max_message_length"] = msg.get(
                "max_message_length",
                self.server_status["max_message_length"],
            )
            self.server_status["rate_limit_messages_per_window"] = msg.get(
                "rate_limit_messages_per_window",
                self.server_status["rate_limit_messages_per_window"],
            )
            self.server_status["rate_limit_window_seconds"] = msg.get(
                "rate_limit_window_seconds",
                self.server_status["rate_limit_window_seconds"],
            )
            self.update_footer()

        elif msg_type == 'error':
            code = msg.get("code", "unknown_error")
            error_message = msg.get("message", "Unknown server error")
            self.add_message("System", f"[{code}] {error_message}", is_system=True)
    
    def update_footer(self):
        """Update header/footer with current server status and username."""
        self.frame.header = self._build_header()
        self.frame.footer = self._build_footer()
    
    def send_message(self, message):
        """Send a message to the server"""
        if not message or not self.socket:
            return
        
        # Validate message
        max_message_length = self.server_status.get("max_message_length") or 1000
        if len(message) > max_message_length:
            self.add_message(
                "System",
                f"Message too long (max {max_message_length} chars)",
                is_system=True,
            )
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
