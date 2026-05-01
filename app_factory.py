"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import os
import secrets
from flask import Flask, jsonify
from utils import id_generator, get_random_color, check_older_than, process_chat
try:
    from rate_limiter import init_limiter
except ModuleNotFoundError:
    def init_limiter(app):
        # Fallback: disable rate limiting if rate_limiter is not available.
        # This keeps containerized installs working even if rate_limiter.py
        # was not included in the image build.
        return app


def _env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable with a safe default."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def register_operational_routes(app: Flask) -> None:
    """Register operational monitoring endpoints."""
    from monitoring import get_health_status, get_chat_stats, get_version

    @app.route('/health', methods=["GET"])
    def health_route():
        return jsonify(get_health_status())

    @app.route('/version', methods=["GET"])
    def version_route():
        return jsonify({"version": get_version()})

    @app.route('/chat/stats', methods=["GET"])
    def chat_stats_route():
        return jsonify(get_chat_stats())


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Set secret key for sessions
    app.secret_key = os.environ.get("OPSECHAT_SECRET_KEY") or secrets.token_urlsafe(64)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Strict")
    app.config.setdefault("SESSION_COOKIE_NAME", "opsechat_session")

    # Safe-by-default profile: keep the public runtime focused on chat.
    extended_services = _env_flag("OPSECHAT_ENABLE_EXTENDED_SERVICES", False)
    app.config["OPSECHAT_ENABLE_EXTENDED_SERVICES"] = extended_services
    app.config["OPSECHAT_ENABLE_LEGACY_CHAT"] = _env_flag(
        "OPSECHAT_ENABLE_LEGACY_CHAT",
        extended_services,
    )
    app.config["OPSECHAT_ENABLE_EMAIL_STACK"] = _env_flag(
        "OPSECHAT_ENABLE_EMAIL_STACK",
        extended_services,
    )
    app.config["OPSECHAT_ENABLE_HTTP_MAIL"] = _env_flag(
        "OPSECHAT_ENABLE_HTTP_MAIL",
        extended_services,
    )
    app.config["OPSECHAT_ENABLE_REVIEWS"] = _env_flag(
        "OPSECHAT_ENABLE_REVIEWS",
        False,
    )
    
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
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        # Checklist:
        # - [ ] Verify that no templates rely on inline <script> or style attributes.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    
    # Register simple chat routes (new simplified interface)
    from simple_chat_routes import register_simple_chat_routes
    register_simple_chat_routes(app)

    if app.config["OPSECHAT_ENABLE_LEGACY_CHAT"]:
        register_chat_routes(app, chatlines, chatters, id_generator, get_random_color,
                            check_older_than, process_chat)
    
    if app.config["OPSECHAT_ENABLE_EMAIL_STACK"]:
        from email_routes import register_email_routes
        register_email_routes(app, id_generator, get_random_color)

    if app.config["OPSECHAT_ENABLE_REVIEWS"]:
        register_review_routes(app, id_generator, get_random_color,
                              add_review_wrapper, get_reviews, get_review_stats)

    if app.config["OPSECHAT_ENABLE_HTTP_MAIL"]:
        from http_mail_routes import register_http_mail_routes
        register_http_mail_routes(app)
    
    # Register MVP console and service manifest routes
    from mvp_routes import register_mvp_routes
    register_mvp_routes(app)

    # Health check endpoint
    from monitoring import get_health_status, get_chat_stats

    @app.route('/health', methods=["GET"])
    def health():
        return jsonify(get_health_status())

    @app.route('/version', methods=["GET"])
    def version():
        health_data = get_health_status()
        return jsonify({
            "version": health_data.get("version", "unknown"),
        })

    # Operational stats endpoint for monitoring dashboards
    @app.route('/chat/stats', methods=["GET"])
    def chat_stats():
        return jsonify(get_chat_stats())
    
    return app
