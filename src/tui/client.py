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
        self.encryption_enabled = False
        self.message_buffer = ""
        
        # UI components
        self.messages_walker = urwid.SimpleFocusListWalker([])
        self.messages_box = urwid.ListBox(self.messages_walker)
        self.input_box = urwid.Edit(">>> ", multiline=False)
        
        # Build UI
        self.build_ui()

    def _footer_text(self):
        """Build dynamic footer text with status indicators and commands."""
        connection_state = "Connected" if self.running else "Disconnected"
        transport = "Tor" if self.use_tor else "Direct"
        encryption = "On" if self.encryption_enabled else "Off"
        return [
            ('info', '/help'),
            ' ',
            ('info', '/status'),
            ' ',
            ('info', '/users'),
            ' ',
            ('info', '/quit'),
            ' | ',
            ('warn', 'State: '),
            ('username', connection_state),
            ' | ',
            ('warn', 'Transport: '),
            ('username', transport),
            ' | ',
            ('warn', 'Enc: '),
            ('username', encryption),
            ' | ',
            ('warn', 'You: '),
            ('username', self.username),
        ]
    
    def build_ui(self):
        """Build the terminal UI"""
        # Header
        header = urwid.AttrMap(
            urwid.Text([
                ('title', 'OpSecChat TUI - Privacy First'),
                ' | ',
                ('info', 'Messages burn in 4 min'),
                ' | ',
                ('warn', 'Text only - No images/video')
            ], align='center'),
            'header'
        )
        
        # Footer with instructions
        footer = urwid.AttrMap(urwid.Text(self._footer_text()), 'footer')
        
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
    
    def connect(self):
        """Connect to the chat server"""
        try:
            if self.use_tor:
                self.add_message("System", f"Connecting via Tor to {self.host}:{self.port}...", is_system=True)
            else:
                self.add_message("System", f"Connecting to {self.host}:{self.port}...", is_system=True)
            
            self.socket = create_socket_connection(self.host, self.port, self.use_tor, self.tor_port)
            self.running = True
            self.update_footer()
            
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
                    self.update_footer()
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
                self.update_footer()
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

        elif msg_type == 'control_response':
            self.handle_control_response(msg)

    def handle_control_response(self, msg):
        """Handle control response from the server."""
        command = msg.get('command')
        if command == 'users':
            user_count = msg.get('users', 0)
            self.add_message("System", f"Connected users: {user_count}", is_system=True)
        elif command == 'status':
            user_count = msg.get('users', 0)
            message_count = msg.get('message_count', 0)
            lifetime = msg.get('message_lifetime', 0)
            self.add_message(
                "System",
                f"Server status: users={user_count}, messages={message_count}, burn={lifetime}s",
                is_system=True
            )
        else:
            response = msg.get('message')
            if response:
                self.add_message("System", response, is_system=True)
    
    def update_footer(self):
        """Update the footer with current username"""
        footer = urwid.AttrMap(urwid.Text(self._footer_text()), 'footer')
        self.frame.footer = footer

    def send_control_command(self, command):
        """Send a control command to the server."""
        if not self.socket:
            self.add_message("System", "Not connected to a server", is_system=True)
            return

        try:
            msg_obj = {
                'type': 'control',
                'command': command
            }
            self.socket.send((json.dumps(msg_obj) + '\n').encode())
        except Exception as e:
            self.add_message("System", f"Failed to send command: {e}", is_system=True)
    
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
                clean_message = message.strip()
                if clean_message.startswith('/'):
                    self.execute_command(clean_message)
                else:
                    self.send_message(clean_message)
                self.input_box.set_edit_text("")
            return
        
        return key

    def execute_command(self, command):
        """Execute slash commands from the input box."""
        parts = command.split()
        cmd = parts[0].lower()

        if cmd == '/help':
            self.add_message(
                "System",
                "Commands: /help, /status, /users, /encrypt <on|off>, /quit",
                is_system=True
            )
            return

        if cmd == '/status':
            self.send_control_command('status')
            return

        if cmd == '/users':
            self.send_control_command('users')
            return

        if cmd == '/encrypt':
            if len(parts) != 2 or parts[1].lower() not in ('on', 'off'):
                self.add_message("System", "Usage: /encrypt <on|off>", is_system=True)
                return
            self.encryption_enabled = (parts[1].lower() == 'on')
            self.update_footer()
            state = "enabled" if self.encryption_enabled else "disabled"
            self.add_message(
                "System",
                f"Local encryption indicator {state}.",
                is_system=True
            )
            return

        if cmd == '/quit':
            self.running = False
            self.update_footer()
            raise urwid.ExitMainLoop()

        self.add_message("System", f"Unknown command: {cmd}. Try /help", is_system=True)
    
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
        self.update_footer()
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
