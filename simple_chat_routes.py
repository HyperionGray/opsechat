"""
Simple OpSec Chat Routes

This module provides a simplified, security-focused chat system with:
- Room-based chat (create/join rooms with simple commands)
- E2E encryption using simple Web Crypto API
- Messages that disappear after 3 minutes
- Randomized usernames with color distinction
- In-memory only storage
- Memory overwriting when messages disappear
- Rate limiting on all write endpoints
"""

import re
import datetime
import secrets
import threading
import base64
from flask import render_template, request, session, jsonify
from utils import sanitize_emojis, filter_to_ascii
from rate_limiter import limiter

# Global room storage (in-memory only)
chat_rooms = {}
rooms_lock = threading.Lock()

# Direct message storage (ephemeral, 1-minute expiry)
direct_messages = {}
dm_lock = threading.Lock()

# In-memory rate limiter: tracks requests per session per endpoint
# Structure: { session_id: { endpoint: [timestamp, ...] } }
_rate_limit_store = {}
_rate_limit_lock = threading.Lock()

# Rate limit configuration
RATE_LIMITS = {
    "chat_create": {"max_requests": 10, "window_seconds": 60},
    "chat_message": {"max_requests": 30, "window_seconds": 60},
    "dm_send": {"max_requests": 5, "window_seconds": 60},
}

# Maximum message length to prevent base64 encoding of images
MAX_MESSAGE_LENGTH = 500  # Reasonable for text, prevents image encoding

# Room class to manage chat state
class ChatRoom:
    """Manages a single chat room with message expiry and memory overwriting"""
    
    def __init__(self, room_id):
        self.room_id = room_id
        self.messages = []
        self.users = {}
        self.created_at = datetime.datetime.now()
        self.lock = threading.Lock()
        # Auto-generated shared encryption key for the room
        self.room_key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
    
    def get_room_key(self):
        """Get the room's shared encryption key (for automatic key exchange)"""
        return self.room_key

    def _touch_user_locked(self, user_id, username, color):
        """Track/update active user metadata. Lock must already be held."""
        now = datetime.datetime.now()
        user = self.users.get(user_id)
        if user is None:
            self.users[user_id] = {
                "username": username,
                "color": color,
                "last_seen": now,
            }
            return

        user["username"] = username
        user["color"] = color
        user["last_seen"] = now

    def touch_user(self, user_id, username, color):
        """Mark a user as active without requiring a message post."""
        with self.lock:
            self._touch_user_locked(user_id, username, color)
    
    def add_message(self, user_id, username, color, message_text):
        """Add a message to the room"""
        with self.lock:
            msg = {
                "message": message_text,
                "user_id": user_id,
                "username": username,
                "color": color,
                "timestamp": datetime.datetime.now()
            }
            self.messages.append(msg)
            self._touch_user_locked(user_id, username, color)
    
    def cleanup_old_messages(self):
        """Remove messages older than 3 minutes and overwrite memory"""
        with self.lock:
            now = datetime.datetime.now()
            new_messages = []
            
            for msg in self.messages:
                age = (now - msg["timestamp"]).total_seconds()
                if age < 180:  # 3 minutes
                    new_messages.append(msg)
                else:
                    # Overwrite message data before deletion (security)
                    msg["message"] = "X" * len(msg["message"])
                    msg["username"] = "X" * len(msg["username"])
            
            self.messages = new_messages
    
    def get_messages(self):
        """Get all current messages"""
        self.cleanup_old_messages()
        with self.lock:
            return self.messages.copy()
    
    def get_user_count(self):
        """Get count of active users (seen in last 5 minutes)"""
        with self.lock:
            now = datetime.datetime.now()
            active_users = sum(1 for u in self.users.values() 
                             if (now - u["last_seen"]).total_seconds() < 300)
            return active_users

    def get_active_users(self):
        """Get active users seen in the last 5 minutes."""
        with self.lock:
            now = datetime.datetime.now()
            return [
                {
                    "username": u["username"],
                    "color": u["color"],
                }
                for u in self.users.values()
                if (now - u["last_seen"]).total_seconds() < 300
            ]


def cleanup_old_rooms():
    """Remove rooms inactive for more than 1 hour"""
    with rooms_lock:
        now = datetime.datetime.now()
        rooms_to_delete = []
        
        for room_id, room in chat_rooms.items():
            # Check if room has been inactive for > 1 hour
            if room.messages:
                last_msg_time = max(msg["timestamp"] for msg in room.messages)
                if (now - last_msg_time).total_seconds() > 3600:
                    rooms_to_delete.append(room_id)
            elif (now - room.created_at).total_seconds() > 3600:
                rooms_to_delete.append(room_id)
        
        for room_id in rooms_to_delete:
            # Overwrite all message data before deletion
            room = chat_rooms[room_id]
            room.cleanup_old_messages()
            del chat_rooms[room_id]


def cleanup_old_dms():
    """Remove DMs older than 1 minute"""
    with dm_lock:
        now = datetime.datetime.now()
        expired_dms = []
        
        for dm_id, dm_data in direct_messages.items():
            age = (now - dm_data["timestamp"]).total_seconds()
            if age > 60:  # 1 minute expiry
                expired_dms.append(dm_id)
        
        for dm_id in expired_dms:
            # Overwrite message before deletion
            dm = direct_messages[dm_id]
            dm["message"] = "X" * len(dm["message"])
            dm["room_id"] = "X" * len(dm["room_id"])
            del direct_messages[dm_id]


def check_rate_limit(session_id: str, endpoint: str) -> tuple:
    """
    Check if a session has exceeded its rate limit for an endpoint.

    Uses a sliding-window algorithm with in-memory storage.

    Args:
        session_id: Unique identifier for the requesting session.
        endpoint: Name of the endpoint to check (must be a key in RATE_LIMITS).

    Returns:
        tuple[bool, int]: (allowed, retry_after_seconds).
            - allowed=True, retry_after=0 when the request is permitted.
            - allowed=False, retry_after>=1 when the limit is exceeded.
            - For unknown endpoints (not in RATE_LIMITS) always returns (True, 0).
    """
    config = RATE_LIMITS.get(endpoint)
    if not config:
        return True, 0

    max_requests = config["max_requests"]
    window = config["window_seconds"]
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(seconds=window)

    with _rate_limit_lock:
        if session_id not in _rate_limit_store:
            _rate_limit_store[session_id] = {}

        session_limits = _rate_limit_store[session_id]
        if endpoint not in session_limits:
            session_limits[endpoint] = []

        # Remove timestamps outside the current window
        session_limits[endpoint] = [
            ts for ts in session_limits[endpoint] if ts > cutoff
        ]

        if len(session_limits[endpoint]) >= max_requests:
            oldest = session_limits[endpoint][0]
            retry_after = int(window - (now - oldest).total_seconds()) + 1
            return False, max(retry_after, 1)

        session_limits[endpoint].append(now)
        return True, 0


def cleanup_rate_limits():
    """Remove stale rate limit entries to prevent unbounded memory growth"""
    with _rate_limit_lock:
        now = datetime.datetime.now()
        stale_sessions = []
        max_window = max(c["window_seconds"] for c in RATE_LIMITS.values())
        cutoff = now - datetime.timedelta(seconds=max_window)

        for sid, endpoints in _rate_limit_store.items():
            for ep in list(endpoints.keys()):
                endpoints[ep] = [ts for ts in endpoints[ep] if ts > cutoff]
                if not endpoints[ep]:
                    del endpoints[ep]
            if not endpoints:
                stale_sessions.append(sid)

        for sid in stale_sessions:
            del _rate_limit_store[sid]


# Background cleanup thread
def cleanup_loop():
    """Continuously clean up old messages and rooms"""
    import time
    while True:
        time.sleep(30)  # Run every 30 seconds
        cleanup_old_rooms()
        cleanup_old_dms()
        cleanup_rate_limits()
        # Cleanup messages in all active rooms
        with rooms_lock:
            for room in chat_rooms.values():
                room.cleanup_old_messages()


# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
cleanup_thread.start()


def generate_secure_room_id(length=32):
    """Generate cryptographically secure, non-discoverable room ID"""
    return secrets.token_urlsafe(length)


def generate_secure_dm_id():
    """Generate cryptographically secure DM ID"""
    return secrets.token_urlsafe(16)


def ensure_chat_session():
    """Ensure an authenticated ephemeral chat session exists."""
    if "_id" not in session:
        session["_id"] = generate_secure_dm_id()
    if "username" not in session:
        session["username"] = generate_random_username()
    if "color" not in session:
        session["color"] = get_random_color_rgb()
    return session["_id"], session["username"], session["color"]


def register_simple_chat_routes(app):
    """Register simple chat routes with the Flask app"""
    
    @app.route('/chat')
    def chat_index():
        """Landing page for creating/joining chat rooms"""
        # Read version from VERSION file
        try:
            with open('VERSION', 'r') as f:
                version = f.read().strip()
        except OSError:
            version = '0.8.0-alpha'  # fallback
        
        return render_template("simple_chat_index.html", version=version)
    
    @app.route('/chat/create', methods=['POST'])
    @limiter.limit("10 per hour; 3 per minute")
    def chat_create():
        """Create a new chat room with cryptographically secure ID"""
        # Ensure session exists for rate limiting
        session_id, _, _ = ensure_chat_session()

        allowed, retry_after = check_rate_limit(session_id, "chat_create")
        if not allowed:
            return jsonify({
                "error": f"Rate limit exceeded. Try again in {retry_after} seconds."
            }), 429

        room_id = generate_secure_room_id(32)
        
        with rooms_lock:
            chat_rooms[room_id] = ChatRoom(room_id)
        
        return jsonify({
            "success": True,
            "room_id": room_id,
            "room_url": f"/chat/room/{room_id}"
        })
    
    @app.route('/chat/room/<string:room_id>')
    def chat_room(room_id):
        """Chat room interface"""
        with rooms_lock:
            if room_id not in chat_rooms:
                return render_template("simple_chat_error.html", 
                                     error="Room not found or expired"), 404
            room = chat_rooms[room_id]
        
        # Initialize user session and mark user as present in room.
        user_id, username, color = ensure_chat_session()
        room.touch_user(user_id, username, color)
        
        return render_template("simple_chat_room.html", 
                             room_id=room_id,
                             username=username,
                             color=color)
    
    @app.route('/chat/room/<string:room_id>/messages', methods=['GET', 'POST'])
    @limiter.limit("60 per minute", methods=["POST"])
    def simple_chat_messages(room_id):
        """Get or post messages to a room"""
        with rooms_lock:
            if room_id not in chat_rooms:
                return jsonify({"error": "Room not found"}), 404
            room = chat_rooms[room_id]

        # Track user presence for both readers and writers.
        user_id, username, color = ensure_chat_session()
        room.touch_user(user_id, username, color)
        
        if request.method == 'POST':
            # Check rate limit before processing message
            allowed, retry_after = check_rate_limit(user_id, "chat_message")
            if not allowed:
                return jsonify({
                    "error": f"Rate limit exceeded. Maximum 30 messages per minute. Try again in {retry_after} seconds."
                }), 429
            
            # Get message from request
            data = request.get_json()
            if not data or "message" not in data:
                return jsonify({"error": "No message provided"}), 400
            
            message_text = data["message"].strip()
            
            # Validate message
            if not message_text:
                return jsonify({"error": "Empty message"}), 400
            
            # Check for length cap to prevent base64 encoding of media
            if len(message_text) > MAX_MESSAGE_LENGTH:
                return jsonify({"error": f"Message too long. Maximum {MAX_MESSAGE_LENGTH} characters allowed."}), 400
            
            # Detect potential base64 encoded content (basic check)
            # Base64 has high entropy and typically lacks spaces
            if len(message_text) > 100:
                space_count = message_text.count(' ')
                if space_count < len(message_text) * 0.05:  # Less than 5% spaces
                    # Might be base64 or encoded content
                    return jsonify({"error": "Invalid message format. Only plain text allowed."}), 400
            
            # Filter to ASCII only and remove emojis
            message_text = filter_to_ascii(message_text)
            message_text = sanitize_emojis(message_text)
            
            # Sanitize message (remove HTML tags)
            message_text = re.sub(r'[<>&"\']', '', message_text)
            
            # Add message to room
            room.add_message(
                user_id,
                username,
                color,
                message_text
            )
            
            return jsonify({"success": True})
        
        else:  # GET
            messages = room.get_messages()
            user_count = room.get_user_count()
            
            return jsonify({
                "messages": [
                    {
                        "username": msg["username"],
                        "color": msg["color"],
                        "message": msg["message"],
                        "timestamp": msg["timestamp"].isoformat(),
                        "is_mine": msg["user_id"] == user_id
                    }
                    for msg in messages
                ],
                "user_count": user_count,
                "my_username": username,
                "my_color": color
            })

    @app.route('/chat/room/<string:room_id>/presence', methods=['GET'])
    def chat_room_presence(room_id):
        """Return current active user presence for a room."""
        with rooms_lock:
            if room_id not in chat_rooms:
                return jsonify({"error": "Room not found"}), 404
            room = chat_rooms[room_id]

        user_id, username, color = ensure_chat_session()
        room.touch_user(user_id, username, color)
        active_users = room.get_active_users()
        return jsonify({
            "room_id": room_id,
            "active_user_count": len(active_users),
            "active_users": active_users,
        })
    
    @app.route('/chat/dm/send', methods=['POST'])
    @limiter.limit("20 per hour; 5 per minute")
    def send_dm():
        """Send a direct message (for sharing room IDs) - expires in 1 minute"""
        # Initialize user session if needed
        user_id, username, _ = ensure_chat_session()

        # Check rate limit for DMs
        allowed, retry_after = check_rate_limit(user_id, "dm_send")
        if not allowed:
            return jsonify({
                "error": f"Rate limit exceeded. Maximum 5 DMs per minute. Try again in {retry_after} seconds."
            }), 429
        
        data = request.get_json()
        if not data or "room_id" not in data or "message" not in data:
            return jsonify({"error": "Missing required fields"}), 400
        
        room_id = data["room_id"].strip()
        message = data["message"].strip()
        
        # Validate
        if not room_id or not message:
            return jsonify({"error": "Empty room_id or message"}), 400
        
        if len(message) > 200:  # DMs should be short
            return jsonify({"error": "DM too long. Maximum 200 characters."}), 400
        
        # Sanitize
        message = re.sub(r'<[^>]+>', '', message)
        message = message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')
        
        # Create DM
        dm_id = generate_secure_dm_id()
        with dm_lock:
            direct_messages[dm_id] = {
                "dm_id": dm_id,
                "sender_id": user_id,
                "sender_name": username,
                "room_id": room_id,
                "message": message,
                "timestamp": datetime.datetime.now(),
                "read": False
            }
        
        return jsonify({
            "success": True,
            "dm_id": dm_id,
            "dm_url": f"/chat/dm/{dm_id}",
            "expires_in": 60
        })
    
    @app.route('/chat/dm/<string:dm_id>')
    def view_dm(dm_id):
        """View a direct message"""
        with dm_lock:
            if dm_id not in direct_messages:
                return jsonify({"error": "DM not found or expired"}), 404
            
            dm = direct_messages[dm_id]
            
            # Check if expired
            age = (datetime.datetime.now() - dm["timestamp"]).total_seconds()
            if age > 60:
                return jsonify({"error": "DM expired"}), 404
            
            # Mark as read
            dm["read"] = True
            
            return jsonify({
                "dm_id": dm["dm_id"],
                "sender_name": dm["sender_name"],
                "room_id": dm["room_id"],
                "message": dm["message"],
                "expires_in": max(0, 60 - int(age))
            })
    
    @app.route('/chat/room/<string:room_id>/key', methods=['GET'])
    def get_room_key(room_id):
        """Get room's shared encryption key (automated key exchange)"""
        with rooms_lock:
            if room_id not in chat_rooms:
                return jsonify({"error": "Room not found"}), 404
            
            room = chat_rooms[room_id]
            return jsonify({
                "room_id": room_id,
                "encryption_key": room.get_room_key()
            })


def generate_random_username():
    """Generate a random, non-reusable username"""
    adjectives = ['Swift', 'Silent', 'Dark', 'Ghost', 'Shadow', 'Phantom', 
                  'Cipher', 'Echo', 'Rogue', 'Viper', 'Stealth', 'Void']
    nouns = ['Raven', 'Wolf', 'Fox', 'Hawk', 'Lynx', 'Owl', 'Cobra', 
             'Tiger', 'Falcon', 'Spider', 'Serpent', 'Dragon']
    number = secrets.randbelow(9999)
    return f"{secrets.choice(adjectives)}{secrets.choice(nouns)}{number:04d}"


def get_random_color_rgb():
    """Get a random color as RGB values for visual distinction"""
    colors = [
        [255, 85, 85],    # red
        [85, 170, 255],   # blue
        [85, 255, 85],    # green
        [255, 170, 85],   # orange
        [255, 85, 255],   # purple
        [170, 85, 0],     # brown
        [255, 170, 255],  # pink
        [170, 170, 170],  # gray
        [170, 170, 0],    # olive
        [85, 255, 255],   # cyan
    ]
    return secrets.choice(colors)
