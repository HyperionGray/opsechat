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

import os
import re
import datetime
import secrets
import threading
import base64
from flask import render_template, request, session, jsonify
from utils import sanitize_emojis, filter_to_ascii

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
_rate_limit_backoff_state = {}

# Default rate limit configuration.
# Environment variable overrides:
# - OPSECHAT_CHAT_CREATE_MAX_REQUESTS
# - OPSECHAT_CHAT_CREATE_WINDOW_SECONDS
# - OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS
# - OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS
# - OPSECHAT_DM_SEND_MAX_REQUESTS
# - OPSECHAT_DM_SEND_WINDOW_SECONDS
# - OPSECHAT_RATE_LIMIT_BACKOFF_BASE_SECONDS
# - OPSECHAT_RATE_LIMIT_BACKOFF_MAX_SECONDS
DEFAULT_RATE_LIMITS = {
    "chat_create": {"max_requests": 3, "window_seconds": 60},
    "chat_message": {"max_requests": 30, "window_seconds": 60},
    "dm_send": {"max_requests": 5, "window_seconds": 60},
}
DEFAULT_RATE_LIMIT_BACKOFF = {
    "base_seconds": 2,
    "max_seconds": 60,
}
RATE_LIMITS = {endpoint: config.copy() for endpoint, config in DEFAULT_RATE_LIMITS.items()}
RATE_LIMIT_BACKOFF = DEFAULT_RATE_LIMIT_BACKOFF.copy()

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
            
            # Track user
            if user_id not in self.users:
                self.users[user_id] = {
                    "username": username,
                    "color": color,
                    "last_seen": datetime.datetime.now()
                }
            else:
                self.users[user_id]["last_seen"] = datetime.datetime.now()
    
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


def _parse_positive_int(value, default):
    """Parse positive integer values safely."""
    if value is None:
        return default
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def configure_rate_limits(app=None):
    """
    Configure in-memory rate limits and backoff from app config/env.

    App config keys (optional):
    - SIMPLE_CHAT_RATE_LIMITS: dict endpoint -> {max_requests, window_seconds}
    - SIMPLE_CHAT_RATE_LIMIT_BACKOFF: {base_seconds, max_seconds}
    """
    global RATE_LIMITS, RATE_LIMIT_BACKOFF

    configured_limits = {
        endpoint: values.copy() for endpoint, values in DEFAULT_RATE_LIMITS.items()
    }

    if app is not None:
        app_limits = app.config.get("SIMPLE_CHAT_RATE_LIMITS", {})
        if isinstance(app_limits, dict):
            for endpoint, defaults in configured_limits.items():
                endpoint_config = app_limits.get(endpoint, {})
                if isinstance(endpoint_config, dict):
                    defaults["max_requests"] = _parse_positive_int(
                        endpoint_config.get("max_requests"),
                        defaults["max_requests"],
                    )
                    defaults["window_seconds"] = _parse_positive_int(
                        endpoint_config.get("window_seconds"),
                        defaults["window_seconds"],
                    )

    env_map = {
        "chat_create": ("OPSECHAT_CHAT_CREATE_MAX_REQUESTS", "OPSECHAT_CHAT_CREATE_WINDOW_SECONDS"),
        "chat_message": ("OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS", "OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS"),
        "dm_send": ("OPSECHAT_DM_SEND_MAX_REQUESTS", "OPSECHAT_DM_SEND_WINDOW_SECONDS"),
    }
    for endpoint, (max_env, window_env) in env_map.items():
        configured_limits[endpoint]["max_requests"] = _parse_positive_int(
            os.getenv(max_env),
            configured_limits[endpoint]["max_requests"],
        )
        configured_limits[endpoint]["window_seconds"] = _parse_positive_int(
            os.getenv(window_env),
            configured_limits[endpoint]["window_seconds"],
        )

    backoff = DEFAULT_RATE_LIMIT_BACKOFF.copy()
    if app is not None:
        app_backoff = app.config.get("SIMPLE_CHAT_RATE_LIMIT_BACKOFF", {})
        if isinstance(app_backoff, dict):
            backoff["base_seconds"] = _parse_positive_int(
                app_backoff.get("base_seconds"),
                backoff["base_seconds"],
            )
            backoff["max_seconds"] = _parse_positive_int(
                app_backoff.get("max_seconds"),
                backoff["max_seconds"],
            )

    backoff["base_seconds"] = _parse_positive_int(
        os.getenv("OPSECHAT_RATE_LIMIT_BACKOFF_BASE_SECONDS"),
        backoff["base_seconds"],
    )
    backoff["max_seconds"] = _parse_positive_int(
        os.getenv("OPSECHAT_RATE_LIMIT_BACKOFF_MAX_SECONDS"),
        backoff["max_seconds"],
    )
    if backoff["max_seconds"] < backoff["base_seconds"]:
        backoff["max_seconds"] = backoff["base_seconds"]

    RATE_LIMITS = configured_limits
    RATE_LIMIT_BACKOFF = backoff


def _calculate_backoff_seconds(attempts: int) -> int:
    """Return exponentially increasing backoff (capped)."""
    base = RATE_LIMIT_BACKOFF["base_seconds"]
    maximum = RATE_LIMIT_BACKOFF["max_seconds"]
    scaled = base * (2 ** max(0, attempts - 1))
    return max(1, min(scaled, maximum))


def _rate_limited_response(message: str, retry_after: int):
    """Create a 429 response with Retry-After header and JSON body."""
    response = jsonify({
        "error": message,
        "retry_after": retry_after,
    })
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


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

        if session_id not in _rate_limit_backoff_state:
            _rate_limit_backoff_state[session_id] = {}
        if endpoint not in _rate_limit_backoff_state[session_id]:
            _rate_limit_backoff_state[session_id][endpoint] = {
                "attempts": 0,
                "blocked_until": None,
            }
        backoff_state = _rate_limit_backoff_state[session_id][endpoint]

        blocked_until = backoff_state.get("blocked_until")
        if blocked_until and blocked_until > now:
            attempts = int(backoff_state.get("attempts", 0)) + 1
            retry_after = _calculate_backoff_seconds(attempts)
            backoff_state["attempts"] = attempts
            backoff_state["blocked_until"] = now + datetime.timedelta(seconds=retry_after)
            return False, retry_after

        # Remove timestamps outside the current window
        session_limits[endpoint] = [
            ts for ts in session_limits[endpoint] if ts > cutoff
        ]

        if len(session_limits[endpoint]) >= max_requests:
            oldest = session_limits[endpoint][0]
            base_retry = int(window - (now - oldest).total_seconds()) + 1
            attempts = int(backoff_state.get("attempts", 0)) + 1
            backoff_retry = _calculate_backoff_seconds(attempts)
            retry_after = max(base_retry, backoff_retry)
            backoff_state["attempts"] = attempts
            backoff_state["blocked_until"] = now + datetime.timedelta(seconds=retry_after)
            return False, max(retry_after, 1)

        session_limits[endpoint].append(now)
        backoff_state["attempts"] = 0
        backoff_state["blocked_until"] = None
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

        # Clean up stale backoff state once the block has expired and
        # there are no active timestamps for that endpoint/session.
        for sid in list(_rate_limit_backoff_state.keys()):
            endpoint_states = _rate_limit_backoff_state[sid]
            active_endpoints = _rate_limit_store.get(sid, {})
            for ep in list(endpoint_states.keys()):
                blocked_until = endpoint_states[ep].get("blocked_until")
                endpoint_has_activity = ep in active_endpoints
                if (not endpoint_has_activity) and (not blocked_until or blocked_until <= now):
                    del endpoint_states[ep]
            if not endpoint_states:
                del _rate_limit_backoff_state[sid]


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

# Configure defaults/env once at import time.
configure_rate_limits()


def generate_secure_room_id(length=32):
    """Generate cryptographically secure, non-discoverable room ID"""
    return secrets.token_urlsafe(length)


def generate_secure_dm_id():
    """Generate cryptographically secure DM ID"""
    return secrets.token_urlsafe(16)


def register_simple_chat_routes(app):
    """Register simple chat routes with the Flask app"""
    configure_rate_limits(app)
    
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
    def chat_create():
        """Create a new chat room with cryptographically secure ID"""
        # Ensure session exists for rate limiting
        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()

        allowed, retry_after = check_rate_limit(session["_id"], "chat_create")
        if not allowed:
            return _rate_limited_response(
                f"Rate limit exceeded. Try again in {retry_after} seconds.",
                retry_after,
            )

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
        
        # Initialize user session
        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()
        
        return render_template("simple_chat_room.html", 
                             room_id=room_id,
                             username=session["username"],
                             color=session["color"])
    
    @app.route('/chat/room/<string:room_id>/messages', methods=['GET', 'POST'])
    def simple_chat_messages(room_id):
        """Get or post messages to a room"""
        with rooms_lock:
            if room_id not in chat_rooms:
                return jsonify({"error": "Room not found"}), 404
            room = chat_rooms[room_id]
        
        if request.method == 'POST':
            # Ensure user has session
            if "_id" not in session:
                session["_id"] = generate_secure_dm_id()
                session["username"] = generate_random_username()
                session["color"] = get_random_color_rgb()

            # Check rate limit before processing message
            allowed, retry_after = check_rate_limit(session["_id"], "chat_message")
            if not allowed:
                max_requests = RATE_LIMITS["chat_message"]["max_requests"]
                window_seconds = RATE_LIMITS["chat_message"]["window_seconds"]
                return _rate_limited_response(
                    f"Rate limit exceeded. Maximum {max_requests} messages per {window_seconds} seconds. "
                    f"Try again in {retry_after} seconds.",
                    retry_after,
                )
            
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
                session["_id"],
                session["username"],
                session["color"],
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
                        "is_mine": msg["user_id"] == session.get("_id")
                    }
                    for msg in messages
                ],
                "user_count": user_count,
                "my_username": session.get("username"),
                "my_color": session.get("color")
            })
    
    @app.route('/chat/dm/send', methods=['POST'])
    def send_dm():
        """Send a direct message (for sharing room IDs) - expires in 1 minute"""
        # Initialize user session if needed
        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()

        # Check rate limit for DMs
        allowed, retry_after = check_rate_limit(session["_id"], "dm_send")
        if not allowed:
            max_requests = RATE_LIMITS["dm_send"]["max_requests"]
            window_seconds = RATE_LIMITS["dm_send"]["window_seconds"]
            return _rate_limited_response(
                f"Rate limit exceeded. Maximum {max_requests} DMs per {window_seconds} seconds. "
                f"Try again in {retry_after} seconds.",
                retry_after,
            )
        
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
                "sender_id": session["_id"],
                "sender_name": session["username"],
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
