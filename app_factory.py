"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

import time

from flask import Flask, jsonify, g, request
from utils import id_generator, get_random_color, check_older_than, process_chat


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
    
    # Track request duration for monitoring
    @app.before_request
    def start_request_timer():
        g.request_start_time = time.perf_counter()

    # Security headers + request metrics
    @app.after_request
    def remove_headers(response):
        response.headers["Server"] = ""
        response.headers["Date"] = ""

        # Record request metrics after every response
        from monitoring import apm

        start_time = getattr(g, "request_start_time", None)
        if start_time is not None:
            response_time = time.perf_counter() - start_time
            endpoint = request.url_rule.rule if request.url_rule else request.path
            apm.record_request(
                endpoint=endpoint,
                method=request.method,
                response_time=response_time,
                status_code=response.status_code,
            )

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
    
    from monitoring import get_health_status, get_readiness_status, apm

    # Primary health endpoint
    @app.route('/health', methods=["GET"])
    def health():
        return jsonify(get_health_status()), 200

    # Liveness endpoint (process is up)
    @app.route('/health/live', methods=["GET"])
    def health_live():
        return jsonify({"status": "alive", "service": "opsechat"}), 200

    # Readiness endpoint (dependencies/subsystems are healthy)
    @app.route('/health/ready', methods=["GET"])
    def health_ready():
        readiness = get_readiness_status()
        status_code = 200 if readiness["status"] == "ready" else 503
        return jsonify(readiness), status_code

    # Lightweight operational metrics summary
    @app.route('/metrics/summary', methods=["GET"])
    def metrics_summary():
        return jsonify(apm.get_metrics_summary()), 200

    # Empty index page to avoid Flask fingerprinting
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