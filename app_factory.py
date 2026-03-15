"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import os
import datetime
from flask import Flask, jsonify, request
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
    started_at = datetime.datetime.now(datetime.timezone.utc)
    
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
    from simple_chat_routes import register_simple_chat_routes
    register_simple_chat_routes(app)
    
    # Register email routes
    from email_routes import register_email_routes
    register_email_routes(app, id_generator, get_random_color)
    
    # Register review routes (existing function-based registration)
    register_review_routes(app, id_generator, get_random_color, 
                          add_review_wrapper, get_reviews, get_review_stats)
    
    # Health endpoint for liveness and lightweight runtime diagnostics.
    @app.route('/health', methods=["GET"])
    def health_check():
        from simple_chat_routes import get_runtime_health_snapshot

        verbose = request.args.get("verbose", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        runtime_snapshot = get_runtime_health_snapshot(include_limits=verbose)
        healthy = runtime_snapshot["cleanup_thread_alive"]

        response = {
            "status": "healthy" if healthy else "degraded",
            "service": "opsechat",
            "version": _read_version(),
            "uptime_seconds": max(
                0,
                int(
                    (
                        datetime.datetime.now(datetime.timezone.utc) - started_at
                    ).total_seconds()
                ),
            ),
            "active_rooms": runtime_snapshot["active_rooms"],
        }
        if verbose:
            response.update({
                "active_dms": runtime_snapshot["active_dms"],
                "rate_limiter_sessions": runtime_snapshot["rate_limiter_sessions"],
                "rate_limit_buckets": runtime_snapshot["rate_limit_buckets"],
                "cleanup_thread_alive": runtime_snapshot["cleanup_thread_alive"],
                "rate_limits": runtime_snapshot["rate_limits"],
            })
        return jsonify(response), 200 if healthy else 503

    @app.route('/health/ready', methods=["GET"])
    def readiness_check():
        """Readiness probe for load balancers and orchestrators."""
        from simple_chat_routes import get_runtime_health_snapshot

        runtime_snapshot = get_runtime_health_snapshot(include_limits=False)
        ready = runtime_snapshot["cleanup_thread_alive"]
        return jsonify({
            "status": "ready" if ready else "not_ready",
            "service": "opsechat",
        }), 200 if ready else 503

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