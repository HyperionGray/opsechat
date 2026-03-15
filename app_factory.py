"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import datetime
import time
from flask import Flask, jsonify
from utils import id_generator, get_random_color, check_older_than, process_chat, read_version


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.config["startup_time"] = time.time()
    
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
    
    # Health check endpoint for monitoring and deployment readiness
    @app.route('/health', methods=["GET"])
    def health_check():
        from simple_chat_routes import (
            chat_rooms,
            rooms_lock,
            _rate_limit_store,
            _rate_limit_lock,
            cleanup_thread,
        )

        with rooms_lock:
            active_rooms = len(chat_rooms)
        with _rate_limit_lock:
            rate_limited_sessions = len(_rate_limit_store)

        version = read_version()
        checks = {
            "version_file": "ok" if version != "unknown" else "degraded",
            "cleanup_worker": "ok" if cleanup_thread.is_alive() else "degraded",
        }
        status = "healthy" if all(result == "ok" for result in checks.values()) else "degraded"
        uptime_seconds = max(0.0, time.time() - app.config["startup_time"])

        return jsonify({
            "status": status,
            "service": "opsechat",
            "version": version,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "uptime_seconds": round(uptime_seconds, 3),
            "active_rooms": active_rooms,
            "rate_limited_sessions": rate_limited_sessions,
            "checks": checks,
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