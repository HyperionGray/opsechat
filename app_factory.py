"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import os
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


def _parse_positive_int_env(var_name, default):
    """Read positive integer env var, falling back to default when invalid."""
    raw_value = os.getenv(var_name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        parsed = int(raw_value)
        if parsed < 1:
            return default
        return parsed
    except ValueError:
        return default


def _load_rate_limit_overrides_from_env():
    """Build simple chat rate-limit config overrides from environment variables."""
    return {
        "chat_create": {
            "max_requests": _parse_positive_int_env(
                "OPSECHAT_RATE_LIMIT_CHAT_CREATE_MAX_REQUESTS", 10
            ),
            "window_seconds": _parse_positive_int_env(
                "OPSECHAT_RATE_LIMIT_CHAT_CREATE_WINDOW_SECONDS", 60
            ),
        },
        "chat_message": {
            "max_requests": _parse_positive_int_env(
                "OPSECHAT_RATE_LIMIT_CHAT_MESSAGE_MAX_REQUESTS", 30
            ),
            "window_seconds": _parse_positive_int_env(
                "OPSECHAT_RATE_LIMIT_CHAT_MESSAGE_WINDOW_SECONDS", 60
            ),
        },
        "dm_send": {
            "max_requests": _parse_positive_int_env(
                "OPSECHAT_RATE_LIMIT_DM_SEND_MAX_REQUESTS", 5
            ),
            "window_seconds": _parse_positive_int_env(
                "OPSECHAT_RATE_LIMIT_DM_SEND_WINDOW_SECONDS", 60
            ),
        },
    }


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Set secret key for sessions
    app.secret_key = id_generator(size=64)
    
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
    
    # Add security headers function
    @app.after_request
    def remove_headers(response):
        response.headers["Server"] = ""
        response.headers["Date"] = ""
        return response
    
    # Register chat routes
    register_chat_routes(app, chatlines, chatters, id_generator, get_random_color, 
                        check_older_than, process_chat, remove_headers)
    
    # Register simple chat routes (new simplified interface)
    from simple_chat_routes import (
        register_simple_chat_routes,
        configure_rate_limits,
        get_rate_limits,
    )
    configure_rate_limits(_load_rate_limit_overrides_from_env())
    register_simple_chat_routes(app)
    
    # Register email routes
    from email_routes import register_email_routes
    register_email_routes(app, id_generator, get_random_color)
    
    # Register review routes (existing function-based registration)
    register_review_routes(app, id_generator, get_random_color, 
                          add_review_wrapper, get_reviews, get_review_stats)
    
    # Health check endpoint for monitoring and deployment readiness
    @app.route('/health', methods=["GET"])
    def health_check():
        from simple_chat_routes import chat_rooms
        return jsonify({
            "status": "healthy",
            "version": _read_version(),
            "active_rooms": len(chat_rooms),
            "service": "opsechat",
            "rate_limits": get_rate_limits(),
        }), 200

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