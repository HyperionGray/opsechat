"""
App Factory for opsechat.

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import os
import time
from datetime import datetime, timezone

from flask import Flask, jsonify

from utils import id_generator, get_random_color, check_older_than, process_chat


def _read_version():
    """Read application version from VERSION file"""
    version_file = os.path.join(os.path.dirname(__file__), "VERSION")
    try:
        with open(version_file) as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Set secret key for sessions
    app.secret_key = id_generator(size=64)

    # Keep process start time for health/readiness reporting
    app.config["START_TIME"] = time.time()

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

    # Apply baseline security/privacy headers to all responses.
    @app.after_request
    def remove_headers(response):
        response.headers["Server"] = "OpSecChat"
        response.headers["Date"] = ""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # Register chat routes
    register_chat_routes(app, chatlines, chatters, id_generator, get_random_color,
                        check_older_than, process_chat, remove_headers)

    # Register simple chat routes (new simplified interface)
    from simple_chat_routes import register_simple_chat_routes
    register_simple_chat_routes(app)

    # Register email routes
    from email_routes import register_email_routes
    register_email_routes(app, id_generator, get_random_color)

    # Register review routes (existing function-based registration)
    register_review_routes(app, id_generator, get_random_color,
                          add_review_wrapper, get_reviews, get_review_stats)

    def _build_health_payload(status: str, ready: bool):
        from simple_chat_routes import chat_rooms, rooms_lock

        with rooms_lock:
            active_rooms = len(chat_rooms)

        uptime_seconds = int(time.time() - app.config["START_TIME"])

        return jsonify({
            "status": status,
            "ready": ready,
            "service": "opsechat",
            "version": _read_version(),
            "active_rooms": active_rooms,
            "uptime_seconds": max(uptime_seconds, 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Health endpoint for monitoring and deployment readiness.
    @app.route('/health', methods=["GET"])
    def health_check():
        return _build_health_payload(status="healthy", ready=True), 200

    @app.route('/health/ready', methods=["GET"])
    def readiness_check():
        is_ready = bool(app.secret_key)
        payload = _build_health_payload(
            status="ready" if is_ready else "degraded",
            ready=is_ready,
        )
        return payload, 200 if is_ready else 503

    # Empty Index page to avoid Flask fingerprinting
    @app.route('/', methods=["GET"])
    def index():
        return ('', 200)

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors with a simple message"""
        return ('Not found', 404)

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        # Log the error but don't expose details to users
        app.logger.error(f'Server Error: {error}')
        return ('Internal server error', 500)

    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 errors"""
        return ('Forbidden', 403)

    return app