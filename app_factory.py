"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

from flask import Flask, jsonify
from utils import id_generator, get_random_color, check_older_than, process_chat
from monitoring import (
    get_health_status,
    get_liveness_status,
    get_readiness_status,
    get_version_info,
)


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
    
    # Status and observability endpoints
    @app.route('/health', methods=["GET"])
    def health():
        """Compatibility health endpoint used by tests and uptime probes."""
        return jsonify(get_health_status())

    @app.route('/health/live', methods=["GET"])
    def health_live():
        """Liveness endpoint: process is running and serving requests."""
        return jsonify(get_liveness_status())

    @app.route('/health/ready', methods=["GET"])
    def health_ready():
        """Readiness endpoint: service is ready for traffic."""
        return jsonify(get_readiness_status())

    @app.route('/version', methods=["GET"])
    def version():
        """Version metadata endpoint sourced from the VERSION file."""
        return jsonify(get_version_info())
    
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