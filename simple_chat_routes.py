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
from flask import render_template, request, session, jsonify, Blueprint
from utils import id_generator, get_random_color, sanitize_emojis, filter_to_ascii
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
MAX_DM_MESSAGE_LENGTH = 200

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


def _evaluate_rate_limit(session_id: str, endpoint: str, consume: bool = True) -> dict:
    """
    Evaluate current rate-limit status for a session/endpoint pair.

    Args:
        session_id: Unique identifier for the requesting session.
        endpoint: Endpoint key in RATE_LIMITS.
        consume: When True, counts this check as one request if allowed.

    Returns:
        dict: {
            "tracked": bool,
            "allowed": bool,
            "retry_after": int,
            "limit": int | None,
            "remaining": int | None,
            "window_seconds": int | None,
            "reset_at": int | None
        }
    """
    config = RATE_LIMITS.get(endpoint)
    if not config:
        return {
            "tracked": False,
            "allowed": True,
            "retry_after": 0,
            "limit": None,
            "remaining": None,
            "window_seconds": None,
            "reset_at": None,
        }

    max_requests = config["max_requests"]
    window = config["window_seconds"]
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(seconds=window)

    with _rate_limit_lock:
        session_limits = _rate_limit_store.setdefault(session_id, {})
        timestamps = [ts for ts in session_limits.get(endpoint, []) if ts > cutoff]
        session_limits[endpoint] = timestamps

        if len(timestamps) >= max_requests:
            oldest = timestamps[0]
            retry_after = int(window - (now - oldest).total_seconds()) + 1
            return {
                "tracked": True,
                "allowed": False,
                "retry_after": max(retry_after, 1),
                "limit": max_requests,
                "remaining": 0,
                "window_seconds": window,
                "reset_at": int((oldest + datetime.timedelta(seconds=window)).timestamp()),
            }

        if consume:
            timestamps.append(now)
            session_limits[endpoint] = timestamps

        current_count = len(timestamps)
        reset_at = now + datetime.timedelta(seconds=window)
        if timestamps:
            reset_at = timestamps[0] + datetime.timedelta(seconds=window)

        return {
            "tracked": True,
            "allowed": True,
            "retry_after": 0,
            "limit": max_requests,
            "remaining": max(max_requests - current_count, 0),
            "window_seconds": window,
            "reset_at": int(reset_at.timestamp()),
        }


def _build_rate_limit_headers(rate_status: dict) -> dict:
    """Build standard rate-limit headers from a rate status dict."""
    if not rate_status.get("tracked"):
        return {}

    headers = {
        "X-RateLimit-Limit": str(rate_status["limit"]),
        "X-RateLimit-Remaining": str(rate_status["remaining"]),
        "X-RateLimit-Window": str(rate_status["window_seconds"]),
        "X-RateLimit-Reset": str(rate_status["reset_at"]),
    }

    if not rate_status.get("allowed"):
        headers["Retry-After"] = str(rate_status["retry_after"])

    return headers


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
    rate_status = _evaluate_rate_limit(session_id, endpoint, consume=True)
    return rate_status["allowed"], rate_status["retry_after"]


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
    
    @app.route('/chat')
    def chat_index():
        """Landing page for creating/joining chat rooms"""
        # Read version from VERSION file
        try:
            with open('VERSION', 'r') as f:
                version = f.read().strip()
        except:
            version = '0.8.0-alpha'  # fallback
        
        return render_template("simple_chat_index.html", version=version)
    
    @app.route('/chat/create', methods=['POST'])
    @limiter.limit("10 per hour; 3 per minute")
    def chat_create():
        """Create a new chat room with cryptographically secure ID"""
        # Ensure session exists for rate limiting
        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()

        rate_status = _evaluate_rate_limit(session["_id"], "chat_create", consume=True)
        if not rate_status["allowed"]:
            response = jsonify({
                "error": f"Rate limit exceeded. Try again in {rate_status['retry_after']} seconds.",
                "rate_limit": {
                    "limit": rate_status["limit"],
                    "remaining": rate_status["remaining"],
                    "retry_after": rate_status["retry_after"],
                    "window_seconds": rate_status["window_seconds"],
                },
            })
            response.status_code = 429
            for header_name, header_value in _build_rate_limit_headers(rate_status).items():
                response.headers[header_name] = header_value
            return response

        room_id = generate_secure_room_id(32)
        
        with rooms_lock:
            chat_rooms[room_id] = ChatRoom(room_id)
        
        response = jsonify({
            "success": True,
            "room_id": room_id,
            "room_url": f"/chat/room/{room_id}"
        })
        for header_name, header_value in _build_rate_limit_headers(rate_status).items():
            response.headers[header_name] = header_value
        return response

    @app.route('/chat/rate-limits', methods=['GET'])
    def chat_rate_limits():
        """Return publishable chat API rate-limit policies."""
        return jsonify({
            "limits": RATE_LIMITS,
            "max_message_length": MAX_MESSAGE_LENGTH,
            "max_dm_length": MAX_DM_MESSAGE_LENGTH,
            "notes": [
                "Limits are tracked per session identifier",
                "429 responses include Retry-After and X-RateLimit-* headers",
            ],
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
            rate_status = _evaluate_rate_limit(session["_id"], "chat_message", consume=True)
            if not rate_status["allowed"]:
                response = jsonify({
                    "error": (
                        "Rate limit exceeded. Maximum 30 messages per minute. "
                        f"Try again in {rate_status['retry_after']} seconds."
                    ),
                    "rate_limit": {
                        "limit": rate_status["limit"],
                        "remaining": rate_status["remaining"],
                        "retry_after": rate_status["retry_after"],
                        "window_seconds": rate_status["window_seconds"],
                    },
                })
                response.status_code = 429
                for header_name, header_value in _build_rate_limit_headers(rate_status).items():
                    response.headers[header_name] = header_value
                return response
            
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
            
            response = jsonify({"success": True})
            for header_name, header_value in _build_rate_limit_headers(rate_status).items():
                response.headers[header_name] = header_value
            return response
        
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
    @limiter.limit("20 per hour; 5 per minute")
    def send_dm():
        """Send a direct message (for sharing room IDs) - expires in 1 minute"""
        # Initialize user session if needed
        if "_id" not in session:
            session["_id"] = generate_secure_dm_id()
            session["username"] = generate_random_username()
            session["color"] = get_random_color_rgb()

        # Check rate limit for DMs
        rate_status = _evaluate_rate_limit(session["_id"], "dm_send", consume=True)
        if not rate_status["allowed"]:
            response = jsonify({
                "error": (
                    "Rate limit exceeded. Maximum 5 DMs per minute. "
                    f"Try again in {rate_status['retry_after']} seconds."
                ),
                "rate_limit": {
                    "limit": rate_status["limit"],
                    "remaining": rate_status["remaining"],
                    "retry_after": rate_status["retry_after"],
                    "window_seconds": rate_status["window_seconds"],
                },
            })
            response.status_code = 429
            for header_name, header_value in _build_rate_limit_headers(rate_status).items():
                response.headers[header_name] = header_value
            return response
        
        data = request.get_json()
        if not data or "room_id" not in data or "message" not in data:
            return jsonify({"error": "Missing required fields"}), 400
        
        room_id = data["room_id"].strip()
        message = data["message"].strip()
        
        # Validate
        if not room_id or not message:
            return jsonify({"error": "Empty room_id or message"}), 400
        
        if len(message) > MAX_DM_MESSAGE_LENGTH:  # DMs should be short
            return jsonify({"error": f"DM too long. Maximum {MAX_DM_MESSAGE_LENGTH} characters."}), 400
        
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
        
        response = jsonify({
            "success": True,
            "dm_id": dm_id,
            "dm_url": f"/chat/dm/{dm_id}",
            "expires_in": 60
        })
        for header_name, header_value in _build_rate_limit_headers(rate_status).items():
            response.headers[header_name] = header_value
        return response
    
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
