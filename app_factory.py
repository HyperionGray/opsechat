"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import os
import re
import secrets
from flask import Flask, jsonify, g
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

    def _inject_csp_nonce(content: str, nonce: str) -> str:
        """Add CSP nonce attributes to inline script/style tags."""
        content = re.sub(
            r"<script(?![^>]*\bnonce=)",
            f'<script nonce="{nonce}"',
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r"<style(?![^>]*\bnonce=)",
            f'<style nonce="{nonce}"',
            content,
            flags=re.IGNORECASE,
        )
        return content

    @app.before_request
    def set_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def inject_template_globals():
        return {"csp_nonce": getattr(g, "csp_nonce", "")}
    
    # Add security headers after every response
    @app.after_request
    def add_security_headers(response):
        nonce = getattr(g, "csp_nonce", secrets.token_urlsafe(16))

        # Keep inline script/style support strict by requiring a per-request nonce.
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type and not response.direct_passthrough:
            body = response.get_data(as_text=True)
            if "<script" in body or "<style" in body:
                response.set_data(_inject_csp_nonce(body, nonce))

        response.headers["Server"] = ""
        response.headers["Date"] = ""
        # Content Security Policy: same-origin resources plus per-response nonce.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'nonce-{nonce}'; "
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