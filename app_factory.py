"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import os
from flask import Flask, jsonify, request
from utils import id_generator, get_random_color, check_older_than, process_chat
try:
    from rate_limiter import init_limiter
except ModuleNotFoundError:
    def init_limiter(app):
        # Fallback: disable rate limiting if rate_limiter is not available.
        # This keeps containerized installs working even if rate_limiter.py
        # was not included in the image build.
        return app


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Set secret key for sessions
    app.secret_key = id_generator(size=64)
    
    # Initialize rate limiter
    init_limiter(app)
    
    # Initialize global state
    chatters = []
    chatlines = []
    reviews = []
    
    # Register function-based routes
    from chat_routes import register_chat_routes
    from review_routes import register_review_routes
    from utils import add_review
    
    # Helper functions for reviews
    def get_reviews():
        return reviews
    
    def get_review_stats():
        if not reviews:
            return {
                "total": 0,
                "average_rating": 0,
                "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            }
        
        total = len(reviews)
        total_rating = sum(review["rating"] for review in reviews)
        average_rating = round(total_rating / total, 1)
        
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            rating_distribution[review["rating"]] += 1
        
        return {
            "total": total,
            "average_rating": average_rating,
            "rating_distribution": rating_distribution
        }
    
    def add_review_wrapper(user_id, rating, review_text):
        return add_review(reviews, user_id, rating, review_text)
    
    # Add security headers after every response
    @app.after_request
    def add_security_headers(response):
        response.headers["Server"] = ""
        response.headers["Date"] = ""
        # Content Security Policy: restrict resources to same origin, block inline scripts
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    
    # Register chat routes
    register_chat_routes(app, chatlines, chatters, id_generator, get_random_color,
                        check_older_than, process_chat)
    
    # Register simple chat routes (new simplified interface)
    from simple_chat_routes import register_simple_chat_routes, RATE_LIMITS
    register_simple_chat_routes(app)

    def _map_rate_limited_endpoint():
        """Map Flask endpoint/path to simple_chat_routes rate-limit keys."""
        endpoint_map = {
            "chat_create": "chat_create",
            "simple_chat_messages": "chat_message",
            "send_dm": "dm_send",
        }
        mapped = endpoint_map.get(request.endpoint)
        if mapped:
            return mapped

        # Fallback for endpoints where Flask may not resolve function names.
        path = request.path or ""
        if request.method == "POST":
            if path == "/chat/create":
                return "chat_create"
            if path == "/chat/dm/send":
                return "dm_send"
            if path.startswith("/chat/room/") and path.endswith("/messages"):
                return "chat_message"
        return None

    @app.errorhandler(429)
    def handle_too_many_requests(error):
        """
        Normalize all 429 responses into a stable JSON contract.

        Flask-Limiter can raise 429 before route handlers run. This keeps
        frontend and tests consistent regardless of where the limit is enforced.
        """
        endpoint_key = _map_rate_limited_endpoint()
        config = RATE_LIMITS.get(endpoint_key, {}) if endpoint_key else {}
        limit = config.get("max_requests")
        window = config.get("window_seconds")

        retry_after = None
        if hasattr(error, "get_response"):
            original = error.get_response()
            retry_after = original.headers.get("Retry-After")

        retry_after_seconds = 1
        if retry_after is not None:
            try:
                retry_after_seconds = max(int(float(retry_after)), 1)
            except (TypeError, ValueError):
                retry_after_seconds = 1

        payload = {
            "error": "Rate limit exceeded. Please retry later.",
            "code": "rate_limited",
            "endpoint": endpoint_key or (request.endpoint or "unknown"),
            "retry_after_seconds": retry_after_seconds,
            "limit": limit,
            "window_seconds": window,
        }

        response = jsonify(payload)
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after_seconds)
        if limit is not None and window is not None:
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Window"] = str(window)
        return response
    
    # Register email routes
    from email_routes import register_email_routes
    register_email_routes(app, id_generator, get_random_color)
    
    # Register review routes (existing function-based registration)
    register_review_routes(app, id_generator, get_random_color, 
                          add_review_wrapper, get_reviews, get_review_stats)

    # Register HTTP mail routes (email over HTTP, no SMTP/IMAP)
    from http_mail_routes import register_http_mail_routes
    register_http_mail_routes(app)
    
    # Health check endpoint
    from monitoring import get_health_status

    @app.route('/health', methods=["GET"])
    def health():
        return jsonify(get_health_status())

    # Empty Index page to avoid Flask fingerprinting
    @app.route('/', methods=["GET"])
    def index():
        return ('', 200)
    
    # CHANGELOG (AI assistant):
    # - Made rate_limiter import optional with a no-op fallback to prevent
    #   ModuleNotFoundError in containerized installs that omit rate_limiter.py.
    #
    # Remaining checklist (non-blocking for runtime):
    # - Update container/Podman build configuration to ensure rate_limiter.py
    #   is included in the image (e.g., COPY list or packaging config).
    # - Once packaging reliably includes rate_limiter.py, consider removing
    #   the fallback or turning it into an explicit configuration option.
    
    return app