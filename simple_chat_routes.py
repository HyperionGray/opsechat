"""
Simple OpSec Chat Routes

This module provides a simplified, security-focused chat system with:
- Room-based chat (create/join rooms with simple commands)
- Closed-roster OpenPGP rooms with explicit epoch-1 membership
- Messages that disappear after 3 minutes
- Randomized usernames with color distinction
- In-memory only storage
- Memory overwriting when messages disappear
- Rate limiting on all write endpoints
"""

import re
import os
import datetime
import secrets
import threading
from flask import render_template, request, session, jsonify
from rate_limiter import limiter
from closed_roster_room import (
    ClosedRosterState,
    OPENPGP_ENVELOPE_TYPE,
)

# Absolute path to this file's directory (used for reliable VERSION lookup)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configurable expiry times (seconds) via environment variables
MESSAGE_EXPIRY_SECONDS = int(os.environ.get('MESSAGE_EXPIRY_SECONDS', 180))  # default 3 min
DM_EXPIRY_SECONDS = int(os.environ.get('DM_EXPIRY_SECONDS', 60))  # default 1 min
ROOM_INACTIVE_SECONDS = int(os.environ.get('ROOM_INACTIVE_SECONDS', 3600))  # default 1 hour

# Global room storage (in-memory only)
chat_rooms = {}
rooms_lock = threading.Lock()

# Direct message storage (ephemeral)
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

# Maximum plaintext message length in the browser UI before OpenPGP wrapping.
MAX_MESSAGE_LENGTH = 500

COLOR_CLASS_NAMES = {
    (255, 85, 85): "user-color-0",
    (85, 170, 255): "user-color-1",
    (85, 255, 85): "user-color-2",
    (255, 170, 85): "user-color-3",
    (255, 85, 255): "user-color-4",
    (170, 85, 0): "user-color-5",
    (255, 170, 255): "user-color-6",
    (170, 170, 170): "user-color-7",
    (170, 170, 0): "user-color-8",
    (85, 255, 255): "user-color-9",
}

# Room class to manage chat state
class ChatRoom:
    """Manages a single chat room with message expiry and memory overwriting"""
    
    def __init__(self, room_id):
        self.room_id = room_id
        self.room_key = secrets.token_urlsafe(32)
        self.messages = []
        self.users = {}
        self.created_at = datetime.datetime.now()
        self.room_key = generate_secure_room_id(32)
        self.lock = threading.Lock()
        self._room_key = secrets.token_urlsafe(32)
        # Legacy compatibility key kept for older tests/integrations that still
        # assert room-level key generation. Closed-roster OpenPGP is the active
        # messaging model and does not use this value for transport encryption.
        self._legacy_room_key = secrets.token_urlsafe(32)
        self.closed_roster = ClosedRosterState(room_id)
        # Backward-compatibility token for legacy room-key callers.
        self._legacy_room_key = secrets.token_urlsafe(32)
    
    def add_message(self, user_id, username, color, message_text):
        """Add a legacy message record; retained for isolated unit tests."""
        payload = {
            "message_type": "legacy_plaintext_test_only",
            "message": message_text,
        }
        self._store_message(user_id, username, color, payload)

    def get_room_key(self):
        """Return a legacy per-room key used by backwards-compatibility tests."""
        return self.room_key

    def _store_message(self, user_id, username, color, payload):
        with self.lock:
            msg = {
                "user_id": user_id,
                "username": username,
                "color": color,
                "timestamp": datetime.datetime.now(),
            }
            msg.update(payload)
            if "message" not in msg and "armored_message" in msg:
                msg["message"] = msg["armored_message"]
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

    def bootstrap_closed_roster(self, members):
        """Initialize the immutable epoch-1 closed roster for this room."""
        with self.lock:
            return self.closed_roster.bootstrap(members)

    def serialize_closed_roster_state(self):
        """Return the room's closed-roster OpenPGP state."""
        with self.lock:
            return self.closed_roster.serialize()

    def get_room_key(self):
        """Return a per-room compatibility key for legacy test/code paths."""
        with self.lock:
            return self._legacy_room_key

    def add_encrypted_message(self, user_id, username, color, payload):
        """Validate and store a closed-roster OpenPGP envelope."""
        with self.lock:
            normalized = self.closed_roster.validate_posted_envelope(payload)
        self._store_message(user_id, username, color, normalized)

    def get_room_key(self):
        """Return the backward-compatible legacy room key token."""
        return self._legacy_room_key
    
    def cleanup_old_messages(self):
        """Remove messages older than 3 minutes and overwrite memory"""
        with self.lock:
            now = datetime.datetime.now()
            new_messages = []
            
            for msg in self.messages:
                age = (now - msg["timestamp"]).total_seconds()
                if age < MESSAGE_EXPIRY_SECONDS:
                    new_messages.append(msg)
                else:
                    # Overwrite message data before deletion (security)
                    for field in (
                        "message",
                        "username",
                        "armored_message",
                        "sender_member_id",
                        "sender_display_name",
                        "sender_signing_fingerprint",
                        "roster_hash",
                    ):
                        value = msg.get(field)
                        if isinstance(value, str):
                            msg[field] = "X" * len(value)
            
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
            # Check if room has been inactive beyond the configured threshold
            if room.messages:
                last_msg_time = max(msg["timestamp"] for msg in room.messages)
                if (now - last_msg_time).total_seconds() > ROOM_INACTIVE_SECONDS:
                    rooms_to_delete.append(room_id)
            elif (now - room.created_at).total_seconds() > ROOM_INACTIVE_SECONDS:
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
            if age > DM_EXPIRY_SECONDS:
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


def register_simple_chat_routes(app):
    """Register simple chat routes with the Flask app"""

    def read_version():
        """Read application version with safe fallback."""
        # Read version from VERSION file (use absolute path so it works regardless of cwd)
        try:
            with open(os.path.join(_BASE_DIR, 'VERSION'), 'r') as f:
                return f.read().strip()
        except (FileNotFoundError, OSError):
            return '0.8.0-alpha'  # fallback

    @app.route('/chat', strict_slashes=False)
    def chat_index():
        """Landing page for creating/joining chat rooms"""
        return render_template("simple_chat_index.html", version=read_version())

    @app.route('/keys', strict_slashes=False)
    def keys_index():
        """Minimal key-management shell while full workflow is in progress."""
        return render_template("keys.html", version=read_version())
    
    @app.route('/chat/create', methods=['POST'])
    @limiter.limit("10 per hour; 3 per minute")
    def chat_create():
        """Create a new chat room with cryptographically secure ID"""
        # Ensure session exists for rate limiting
        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()

        allowed, retry_after = check_rate_limit(session["_id"], "chat_create")
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
        
        # Initialize user session
        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()
        
        return render_template(
            "simple_chat_room.html",
            room_id=room_id,
            max_message_length=MAX_MESSAGE_LENGTH,
        )

    @app.route('/chat/room/<string:room_id>/state', methods=['GET'])
    def simple_chat_room_state(room_id):
        """Get the closed-roster OpenPGP state for a room."""
        with rooms_lock:
            if room_id not in chat_rooms:
                return jsonify({"error": "Room not found"}), 404
            room = chat_rooms[room_id]

        return jsonify(room.serialize_closed_roster_state())

    @app.route('/chat/room/<string:room_id>/state/bootstrap', methods=['POST'])
    @limiter.limit("10 per hour; 3 per minute")
    def bootstrap_simple_chat_room(room_id):
        """Lock a room to an immutable epoch-1 OpenPGP roster."""
        with rooms_lock:
            if room_id not in chat_rooms:
                return jsonify({"error": "Room not found"}), 404
            room = chat_rooms[room_id]

        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()

        data = request.get_json(silent=True)
        members = data.get("members") if isinstance(data, dict) else None
        if not members:
            return jsonify({"error": "No roster members provided"}), 400

        try:
            state = room.bootstrap_closed_roster(members)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        session["room_member_ids"] = session.get("room_member_ids", {})
        creator_member_id = data.get("creator_member_id") if isinstance(data, dict) else None
        if isinstance(creator_member_id, str) and creator_member_id.strip():
            session["room_member_ids"][room_id] = creator_member_id.strip()
            session.modified = True

        return jsonify({"success": True, **state})
    
    @app.route('/chat/room/<string:room_id>/messages', methods=['GET', 'POST'])
    @limiter.limit("60 per minute", methods=["POST"])
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
                return jsonify({
                    "error": f"Rate limit exceeded. Maximum 30 messages per minute. Try again in {retry_after} seconds."
                }), 429
            
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({"error": "No message provided"}), 400

            try:
                room.add_encrypted_message(
                    session["_id"],
                    session["username"],
                    session["color"],
                    data,
                )
            except (TypeError, ValueError) as exc:
                if "not initialized" in str(exc):
                    return jsonify({
                        "error": "Room roster is not initialized. Bootstrap the closed roster before messaging."
                    }), 409
                return jsonify({"error": str(exc)}), 400

            sender_member_id = data.get("sender_member_id")
            if isinstance(sender_member_id, str) and sender_member_id.strip():
                room_member_ids = session.get("room_member_ids", {})
                room_member_ids[room_id] = sender_member_id.strip()
                session["room_member_ids"] = room_member_ids
                session.modified = True

            return jsonify({"success": True})
        
        else:  # GET
            messages = room.get_messages()
            user_count = room.get_user_count()
            room_member_id = session.get("room_member_ids", {}).get(room_id)
            
            return jsonify({
                "messages": [
                    {
                        "message_type": msg.get("message_type"),
                        "username": msg.get("sender_display_name", msg["username"]),
                        "color": msg["color"],
                        "color_class": get_color_class_name(msg["color"]),
                        "message": msg["message"],
                        "armored_message": msg.get("armored_message", msg["message"]),
                        "sender_member_id": msg.get("sender_member_id"),
                        "sender_display_name": msg.get("sender_display_name"),
                        "sender_signing_fingerprint": msg.get("sender_signing_fingerprint"),
                        "epoch": msg.get("epoch"),
                        "roster_hash": msg.get("roster_hash"),
                        "timestamp": msg["timestamp"].isoformat(),
                        "is_mine": msg.get("sender_member_id") == room_member_id,
                    }
                    for msg in messages
                ],
                "user_count": user_count,
                "my_username": session.get("username"),
                "my_color": session.get("color"),
                "my_member_id": room_member_id,
            })
    
    @app.route('/chat/dm/send', methods=['POST'])
    @limiter.limit("20 per hour; 5 per minute")
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
            "expires_in": DM_EXPIRY_SECONDS
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
            if age > DM_EXPIRY_SECONDS:
                return jsonify({"error": "DM expired"}), 404
            
            # Mark as read
            dm["read"] = True
            
            return jsonify({
                "dm_id": dm["dm_id"],
                "sender_name": dm["sender_name"],
                "room_id": dm["room_id"],
                "message": dm["message"],
                "expires_in": max(0, DM_EXPIRY_SECONDS - int(age))
            })
    
    @app.route('/chat/room/<string:room_id>/key', methods=['GET'])
    def get_room_key(room_id):
        """Deprecated insecure endpoint kept only as an explicit failure path."""
        with rooms_lock:
            if room_id not in chat_rooms:
                return jsonify({"error": "Room not found"}), 404

        return jsonify({
            "error": (
                "The shared room-key endpoint is retired. "
                "Use the closed-roster OpenPGP room bootstrap flow instead."
            ),
            "deprecated": True,
            "replacement": f"/chat/room/{room_id}/state",
            "mode": OPENPGP_ENVELOPE_TYPE,
        }), 410


def generate_random_username():
    """Generate a random, non-reusable username"""
    adjectives = ['Swift', 'Silent', 'Dark', 'Ghost', 'Shadow', 'Phantom', 
                  'Cipher', 'Echo', 'Rogue', 'Viper', 'Stealth', 'Void']
    nouns = ['Raven', 'Wolf', 'Fox', 'Hawk', 'Lynx', 'Owl', 'Cobra', 
             'Tiger', 'Falcon', 'Spider', 'Serpent', 'Dragon']
    number = secrets.randbelow(9999)
    return f"{secrets.choice(adjectives)}{secrets.choice(nouns)}{number:04d}"


def get_color_class_name(color):
    """Return the CSS class name for a known chat color."""
    return COLOR_CLASS_NAMES.get(tuple(color), "")


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
