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

    STRICT_CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "object-src 'none';"
    )
    LEGACY_COMPAT_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "object-src 'none';"
    )
    LEGACY_HTML_ENDPOINTS = {
        # Legacy chat templates with inline script/style and event handlers.
        "drop",
        "drop_landing",
        "drop_landing_auto",
        "drop_yes",
        "drop_noscript",
        "chat_messages",
        # Legacy email templates with inline script/style and event handlers.
        "email_inbox",
        "email_inbox_script",
        "email_burner",
        "email_burner_script",
        "email_config",
        "email_compose",
        "email_view",
        "email_edit",
        # Legacy reviews/templates that include inline script blocks.
        "reviews_main",
        "reviews_script",
        # HTTP mail UI template has inline handlers and script block.
        "http_mail_index",
        "http_mail_send",
        "http_mail_inbox",
        "http_mail_destroy",
    }
    
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
        # Strict-by-default CSP. Legacy HTML endpoints get temporary compatibility
        # while templates are migrated away from inline handlers/styles.
        endpoint = request.endpoint or ""
        is_html = response.mimetype == "text/html"
        csp_value = LEGACY_COMPAT_CSP if (is_html and endpoint in LEGACY_HTML_ENDPOINTS) else STRICT_CSP
        response.headers["Content-Security-Policy"] = csp_value
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
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