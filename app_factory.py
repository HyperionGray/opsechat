"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import os

from flask import Flask
from utils import id_generator, get_random_color, check_older_than, process_chat
from rate_limiter import init_limiter, ensure_rate_limit_client_id


def create_app(config_overrides=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Set secret key for sessions
    app.secret_key = os.getenv("OPSECHAT_SECRET_KEY", id_generator(size=64))

    strict_csp = os.getenv("OPSECHAT_STRICT_CSP", "0").lower() in {"1", "true", "yes"}
    default_csp_compatible = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )
    default_csp_strict = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )

    app.config.setdefault("RATE_LIMIT_CHAT_CREATE", "10 per hour; 3 per minute")
    app.config.setdefault("RATE_LIMIT_CHAT_MESSAGES_POST", "60 per minute")
    app.config.setdefault("RATE_LIMIT_CHAT_DM_SEND", "20 per hour; 5 per minute")
    app.config.setdefault("CONTENT_SECURITY_POLICY", default_csp_strict if strict_csp else default_csp_compatible)
    app.config.setdefault("X_FRAME_OPTIONS", "SAMEORIGIN")
    app.config.setdefault("REFERRER_POLICY", "no-referrer")

    if config_overrides:
        app.config.update(config_overrides)

    # Ensure each client gets a stable session key before limiter accounting.
    @app.before_request
    def initialize_rate_limit_identity():
        ensure_rate_limit_client_id()

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
        response.headers["Content-Security-Policy"] = app.config["CONTENT_SECURITY_POLICY"]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = app.config["X_FRAME_OPTIONS"]
        response.headers["Referrer-Policy"] = app.config["REFERRER_POLICY"]
        return response
    
    # Register chat routes
    register_chat_routes(app, chatlines, chatters, id_generator, get_random_color, 
                        check_older_than, process_chat)
    
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