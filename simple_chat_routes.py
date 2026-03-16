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
import os
from copy import deepcopy
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

# Rate limit configuration (custom limiter with configurable backoff)
DEFAULT_RATE_LIMITS = {
    "chat_create": {"max_requests": 3, "window_seconds": 60, "hourly_max_requests": 10},
    "chat_message": {"max_requests": 30, "window_seconds": 60, "hourly_max_requests": None},
    "dm_send": {"max_requests": 5, "window_seconds": 60, "hourly_max_requests": 20},
}

DEFAULT_BACKOFF_POLICY = {
    "enabled": True,
    "base_seconds": 2,
    "max_seconds": 60,
    "multiplier": 2,
}

RATE_LIMITS = deepcopy(DEFAULT_RATE_LIMITS)
BACKOFF_POLICY = deepcopy(DEFAULT_BACKOFF_POLICY)

# Maximum message length to prevent base64 encoding of images
MAX_MESSAGE_LENGTH = 500  # Reasonable for text, prevents image encoding


def _safe_positive_int(value, fallback):
    """Parse positive integers defensively."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _safe_optional_positive_int(value, fallback):
    """Parse optional positive integers defensively."""
    if value in (None, ""):
        return fallback
    return _safe_positive_int(value, fallback)


def _safe_bool(value, fallback):
    """Parse booleans from bool/string values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return fallback


def configure_rate_limit_settings(app=None):
    """
    Configure runtime rate limits/backoff from env and Flask app config.

    Supported app config keys:
      - SIMPLE_CHAT_RATE_LIMITS (dict keyed by endpoint)
      - SIMPLE_CHAT_BACKOFF_POLICY (dict)
    """
    global RATE_LIMITS, BACKOFF_POLICY

    configured_limits = deepcopy(DEFAULT_RATE_LIMITS)
    configured_backoff = deepcopy(DEFAULT_BACKOFF_POLICY)

    # Environment overrides
    for endpoint, defaults in configured_limits.items():
        env_prefix = f"OPSECHAT_RATE_LIMIT_{endpoint.upper()}"
        configured_limits[endpoint]["max_requests"] = _safe_positive_int(
            os.environ.get(f"{env_prefix}_MAX_REQUESTS"),
            defaults["max_requests"],
        )
        configured_limits[endpoint]["window_seconds"] = _safe_positive_int(
            os.environ.get(f"{env_prefix}_WINDOW_SECONDS"),
            defaults["window_seconds"],
        )
        configured_limits[endpoint]["hourly_max_requests"] = _safe_optional_positive_int(
            os.environ.get(f"{env_prefix}_HOURLY_MAX_REQUESTS"),
            defaults["hourly_max_requests"],
        )

    configured_backoff["enabled"] = _safe_bool(
        os.environ.get("OPSECHAT_RATE_LIMIT_BACKOFF_ENABLED"),
        configured_backoff["enabled"],
    )
    configured_backoff["base_seconds"] = _safe_positive_int(
        os.environ.get("OPSECHAT_RATE_LIMIT_BACKOFF_BASE_SECONDS"),
        configured_backoff["base_seconds"],
    )
    configured_backoff["max_seconds"] = _safe_positive_int(
        os.environ.get("OPSECHAT_RATE_LIMIT_BACKOFF_MAX_SECONDS"),
        configured_backoff["max_seconds"],
    )
    configured_backoff["multiplier"] = _safe_positive_int(
        os.environ.get("OPSECHAT_RATE_LIMIT_BACKOFF_MULTIPLIER"),
        configured_backoff["multiplier"],
    )

    # App config overrides (higher precedence)
    if app is not None:
        app_limits = app.config.get("SIMPLE_CHAT_RATE_LIMITS", {})
        if isinstance(app_limits, dict):
            for endpoint, endpoint_overrides in app_limits.items():
                if endpoint not in configured_limits or not isinstance(endpoint_overrides, dict):
                    continue
                defaults = configured_limits[endpoint]
                defaults["max_requests"] = _safe_positive_int(
                    endpoint_overrides.get("max_requests"), defaults["max_requests"]
                )
                defaults["window_seconds"] = _safe_positive_int(
                    endpoint_overrides.get("window_seconds"), defaults["window_seconds"]
                )
                defaults["hourly_max_requests"] = _safe_optional_positive_int(
                    endpoint_overrides.get("hourly_max_requests"),
                    defaults["hourly_max_requests"],
                )

        app_backoff = app.config.get("SIMPLE_CHAT_BACKOFF_POLICY", {})
        if isinstance(app_backoff, dict):
            configured_backoff["enabled"] = _safe_bool(
                app_backoff.get("enabled"), configured_backoff["enabled"]
            )
            configured_backoff["base_seconds"] = _safe_positive_int(
                app_backoff.get("base_seconds"), configured_backoff["base_seconds"]
            )
            configured_backoff["max_seconds"] = _safe_positive_int(
                app_backoff.get("max_seconds"), configured_backoff["max_seconds"]
            )
            configured_backoff["multiplier"] = _safe_positive_int(
                app_backoff.get("multiplier"), configured_backoff["multiplier"]
            )

    RATE_LIMITS = configured_limits
    BACKOFF_POLICY = configured_backoff


def _build_flask_limiter_rule(endpoint):
    """
    Build coarse Flask-Limiter rule strings from configuration.

    Flask-Limiter acts as a broad safety net while custom limiter enforces
    per-session windows and adaptive backoff.
    """
    config = RATE_LIMITS.get(endpoint, {})
    hourly_max = config.get("hourly_max_requests")
    if hourly_max:
        return f"{hourly_max} per hour"

    # Keep this looser than the custom limiter to avoid shadowing backoff logic.
    window_seconds = max(_safe_positive_int(config.get("window_seconds"), 60), 1)
    max_requests = _safe_positive_int(config.get("max_requests"), 30)
    coarse_limit = max_requests * 4
    return f"{coarse_limit} per {window_seconds} second"

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


def _normalize_endpoint_state(raw_state):
    """Normalize legacy/new endpoint state shapes into one dict format."""
    if isinstance(raw_state, list):
        timestamps = [ts for ts in raw_state if isinstance(ts, datetime.datetime)]
        return {"timestamps": timestamps, "violations": 0, "blocked_until": None}

    if not isinstance(raw_state, dict):
        return {"timestamps": [], "violations": 0, "blocked_until": None}

    timestamps = raw_state.get("timestamps", [])
    if not isinstance(timestamps, list):
        timestamps = []
    timestamps = [ts for ts in timestamps if isinstance(ts, datetime.datetime)]

    violations = _safe_positive_int(raw_state.get("violations", 0), 0)
    if violations < 0:
        violations = 0

    blocked_until = raw_state.get("blocked_until")
    if not isinstance(blocked_until, datetime.datetime):
        blocked_until = None

    return {
        "timestamps": timestamps,
        "violations": violations,
        "blocked_until": blocked_until,
    }


def _compute_backoff_seconds(violations):
    """Compute adaptive backoff from current violation streak."""
    if not BACKOFF_POLICY.get("enabled", True):
        return 0
    if violations <= 0:
        return 0

    base_seconds = _safe_positive_int(BACKOFF_POLICY.get("base_seconds"), 2)
    max_seconds = _safe_positive_int(BACKOFF_POLICY.get("max_seconds"), 60)
    multiplier = _safe_positive_int(BACKOFF_POLICY.get("multiplier"), 2)

    backoff = base_seconds * (multiplier ** (violations - 1))
    return min(backoff, max_seconds)


def get_rate_limit_decision(session_id: str, endpoint: str) -> dict:
    """
    Return a detailed rate-limit decision for one session+endpoint.

    Response shape:
      {
        "allowed": bool,
        "retry_after_seconds": int,
        "backoff_level": int,
        "max_requests": int,
        "window_seconds": int,
        "remaining_requests": int,
      }
    """
    config = RATE_LIMITS.get(endpoint)
    if not config:
        return {
            "allowed": True,
            "retry_after_seconds": 0,
            "backoff_level": 0,
            "max_requests": 0,
            "window_seconds": 0,
            "remaining_requests": 0,
        }

    max_requests = _safe_positive_int(config.get("max_requests"), 1)
    window_seconds = _safe_positive_int(config.get("window_seconds"), 60)
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(seconds=window_seconds)

    with _rate_limit_lock:
        session_limits = _rate_limit_store.setdefault(session_id, {})
        endpoint_state = _normalize_endpoint_state(session_limits.get(endpoint))
        session_limits[endpoint] = endpoint_state

        endpoint_state["timestamps"] = [
            ts for ts in endpoint_state["timestamps"] if ts > cutoff
        ]

        # Honor existing temporary block from exponential backoff.
        blocked_until = endpoint_state.get("blocked_until")
        if blocked_until and now < blocked_until:
            retry_after = max(int((blocked_until - now).total_seconds()) + 1, 1)
            return {
                "allowed": False,
                "retry_after_seconds": retry_after,
                "backoff_level": endpoint_state["violations"],
                "max_requests": max_requests,
                "window_seconds": window_seconds,
                "remaining_requests": 0,
            }

        endpoint_state["blocked_until"] = None

        if len(endpoint_state["timestamps"]) >= max_requests:
            oldest = endpoint_state["timestamps"][0]
            window_retry_after = int(window_seconds - (now - oldest).total_seconds()) + 1
            endpoint_state["violations"] += 1
            backoff_retry_after = _compute_backoff_seconds(endpoint_state["violations"])
            retry_after = max(max(window_retry_after, 1), backoff_retry_after)
            endpoint_state["blocked_until"] = now + datetime.timedelta(seconds=retry_after)
            return {
                "allowed": False,
                "retry_after_seconds": retry_after,
                "backoff_level": endpoint_state["violations"],
                "max_requests": max_requests,
                "window_seconds": window_seconds,
                "remaining_requests": 0,
            }

        endpoint_state["timestamps"].append(now)
        # Successful traffic decays penalty streak gradually.
        endpoint_state["violations"] = max(0, endpoint_state["violations"] - 1)
        remaining_requests = max(max_requests - len(endpoint_state["timestamps"]), 0)
        return {
            "allowed": True,
            "retry_after_seconds": 0,
            "backoff_level": endpoint_state["violations"],
            "max_requests": max_requests,
            "window_seconds": window_seconds,
            "remaining_requests": remaining_requests,
        }


def check_rate_limit(session_id: str, endpoint: str) -> tuple:
    """
    Backward-compatible wrapper returning (allowed, retry_after_seconds).
    """
    decision = get_rate_limit_decision(session_id, endpoint)
    return decision["allowed"], decision["retry_after_seconds"]


def cleanup_rate_limits():
    """Remove stale rate limit entries to prevent unbounded memory growth"""
    with _rate_limit_lock:
        now = datetime.datetime.now()
        stale_sessions = []
        max_window = max(c["window_seconds"] for c in RATE_LIMITS.values())
        cutoff = now - datetime.timedelta(seconds=max_window)

        for sid, endpoints in _rate_limit_store.items():
            for ep in list(endpoints.keys()):
                endpoint_state = _normalize_endpoint_state(endpoints[ep])
                endpoint_state["timestamps"] = [
                    ts for ts in endpoint_state["timestamps"] if ts > cutoff
                ]
                blocked_until = endpoint_state.get("blocked_until")
                is_temporarily_blocked = isinstance(blocked_until, datetime.datetime) and blocked_until > now

                if not endpoint_state["timestamps"] and not is_temporarily_blocked:
                    del endpoints[ep]
                else:
                    endpoints[ep] = endpoint_state
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


def _rate_limited_json_response(error_message, decision):
    """Build a consistent 429 response payload with retry metadata."""
    response = jsonify({
        "error": error_message,
        "retry_after_seconds": decision["retry_after_seconds"],
        "backoff_level": decision["backoff_level"],
        "max_requests": decision["max_requests"],
        "window_seconds": decision["window_seconds"],
    })
    response.status_code = 429
    response.headers["Retry-After"] = str(decision["retry_after_seconds"])
    response.headers["X-RateLimit-Backoff-Level"] = str(decision["backoff_level"])
    return response


def register_simple_chat_routes(app):
    """Register simple chat routes with the Flask app"""
    configure_rate_limit_settings(app)
    
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
    @limiter.limit(lambda: _build_flask_limiter_rule("chat_create"))
    def chat_create():
        """Create a new chat room with cryptographically secure ID"""
        # Ensure session exists for rate limiting
        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()

        decision = get_rate_limit_decision(session["_id"], "chat_create")
        if not decision["allowed"]:
            return _rate_limited_json_response(
                f"Rate limit exceeded. Try again in {decision['retry_after_seconds']} seconds.",
                decision,
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
    @limiter.limit(lambda: _build_flask_limiter_rule("chat_message"), methods=["POST"])
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
            decision = get_rate_limit_decision(session["_id"], "chat_message")
            if not decision["allowed"]:
                return _rate_limited_json_response(
                    (
                        "Rate limit exceeded. Maximum "
                        f"{decision['max_requests']} messages per "
                        f"{decision['window_seconds']} seconds. "
                        f"Try again in {decision['retry_after_seconds']} seconds."
                    ),
                    decision,
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
    @limiter.limit(lambda: _build_flask_limiter_rule("dm_send"))
    def send_dm():
        """Send a direct message (for sharing room IDs) - expires in 1 minute"""
        # Initialize user session if needed
        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()

        # Check rate limit for DMs
        decision = get_rate_limit_decision(session["_id"], "dm_send")
        if not decision["allowed"]:
            return _rate_limited_json_response(
                (
                    "Rate limit exceeded. Maximum "
                    f"{decision['max_requests']} DMs per "
                    f"{decision['window_seconds']} seconds. "
                    f"Try again in {decision['retry_after_seconds']} seconds."
                ),
                decision,
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
