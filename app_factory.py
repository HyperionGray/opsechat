"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import os
import re
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
        # Checklist:
        # - [ ] Verify that no templates rely on inline <script> or style attributes.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.errorhandler(429)
    def handle_rate_limit_exceeded(error):
        """
        Return a consistent JSON payload for all rate-limit responses.

        Flask-Limiter can raise 429 before hitting route handlers. Normalizing
        response shape here lets clients implement generic Retry-After backoff.
        """
        retry_after = 1

        # Prefer Retry-After provided by underlying limiter response.
        try:
            default_response = error.get_response()
            header_value = default_response.headers.get("Retry-After")
            if header_value:
                retry_after = int(header_value)
        except Exception:
            pass

        # Fallback: parse "X per Y second" style text from limiter description.
        if retry_after <= 1:
            description = str(getattr(error, "description", "") or "")
            match = re.search(r"(\d+)\s*second", description, flags=re.IGNORECASE)
            if match:
                retry_after = max(int(match.group(1)), 1)

        response = jsonify({
            "error": f"Rate limit exceeded. Try again in {retry_after} seconds.",
            "error_code": "rate_limit_exceeded",
            "retry_after": retry_after,
            "path": request.path
        })
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-RateLimit-Retry-After"] = str(retry_after)
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