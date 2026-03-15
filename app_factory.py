"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import os
from flask import Flask, jsonify, request
from utils import id_generator, get_random_color, check_older_than, process_chat
from rate_limiter import init_limiter


def create_app(test_config=None):
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Set secret key for sessions
    app.secret_key = id_generator(size=64)

    # Configurable per-endpoint limits for chat write APIs
    app.config.setdefault("RATE_LIMIT_CHAT_CREATE", os.getenv("OPSECHAT_RATE_LIMIT_CHAT_CREATE", "10 per hour; 3 per minute"))
    app.config.setdefault("RATE_LIMIT_CHAT_MESSAGES_POST", os.getenv("OPSECHAT_RATE_LIMIT_CHAT_MESSAGES_POST", "60 per minute"))
    app.config.setdefault("RATE_LIMIT_CHAT_DM_SEND", os.getenv("OPSECHAT_RATE_LIMIT_CHAT_DM_SEND", "20 per hour; 5 per minute"))
    if test_config:
        app.config.update(test_config)
    
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
        # Content Security Policy: keep resources same-origin and only allow same-origin framing.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'self';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.errorhandler(429)
    def handle_rate_limit(error):
        """Return JSON for API clients and plain text for browser pages."""
        retry_after = int(getattr(error, "retry_after", 0) or 0)
        is_api_request = (
            request.path.startswith("/chat/")
            or request.path.endswith(".json")
            or request.accept_mimetypes.best == "application/json"
        )
        if is_api_request:
            response = jsonify({"error": "Rate limit exceeded. Please retry later."})
        else:
            response = app.response_class(
                "Rate limit exceeded. Please retry later.",
                mimetype="text/plain",
            )

        response.status_code = 429
        if retry_after > 0:
            response.headers["Retry-After"] = str(retry_after)
        return response
    
    # Register chat routes
    register_chat_routes(
        app,
        chatlines,
        chatters,
        id_generator,
        get_random_color,
        check_older_than,
        process_chat,
    )
    
    # Register simple chat routes (new simplified interface)
    from simple_chat_routes import register_simple_chat_routes
    register_simple_chat_routes(app)
    
    # Register email routes
    from email_routes import register_email_routes
    register_email_routes(app, id_generator, get_random_color)
    
    # Register review routes (existing function-based registration)
    register_review_routes(app, id_generator, get_random_color, 
                          add_review_wrapper, get_reviews, get_review_stats)
    
    # Empty Index page to avoid Flask fingerprinting
    @app.route('/', methods=["GET"])
    def index():
        return ('', 200)
    
    return app