"""
App Factory for opsechat

This module handles Flask application creation and configuration,
extracted from runserver.py to improve code organization.
"""

from flask import Flask
from utils import id_generator


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Set secret key for sessions
    app.secret_key = id_generator(size=64)
    
    # Register blueprints and function-based routes
    from burner_routes import burner_bp
    from security_routes import security_bp
    from landing_routes import landing_bp
    from review_routes import register_review_routes
    from email_routes import register_email_routes
    from utils import get_random_color
    
    # Register blueprints
    app.register_blueprint(burner_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(landing_bp)
    
    # Register function-based routes
    register_review_routes(app)
    register_email_routes(app, id_generator, get_random_color)
    
    # Add security headers
    @app.after_request
    def remove_headers(response):
        response.headers["Server"] = ""
        response.headers["Date"] = ""
        return response
    
    # Empty Index page to avoid Flask fingerprinting
    @app.route('/', methods=["GET"])
    def index():
        return ('', 200)
    
    return app