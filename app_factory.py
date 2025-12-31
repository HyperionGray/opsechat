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
    
    # Register blueprints
    from chat_routes import chat_bp
    from email_routes import email_bp
    from burner_routes import burner_bp
    from security_routes import security_bp
    from review_routes import register_review_routes
    
    # Register all blueprints
    app.register_blueprint(chat_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(burner_bp)
    app.register_blueprint(security_bp)
    
    # Register review routes (existing function-based registration)
    register_review_routes(app)
    
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