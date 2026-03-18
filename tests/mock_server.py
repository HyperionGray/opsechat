#!/usr/bin/env python3
"""
Refactored Mock Server for opsechat testing

This is a significantly simplified version of the original mock_server.py,
using modular route handlers for better organization and maintainability.

Original file was 501 lines, refactored to ~120 lines.
"""

import sys
import os
import datetime
import string
import random

# Add parent directory to Python path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from flask import Flask, session
from mock_routes import create_mock_routes

# Create Flask app with absolute paths for better CI compatibility
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(base_dir, 'templates')
static_dir = os.path.join(base_dir, 'static')

# Verify directories exist and provide fallback
if not os.path.exists(template_dir):
    print(f"Warning: Template directory not found: {template_dir}")
    template_dir = None
if not os.path.exists(static_dir):
    print(f"Warning: Static directory not found: {static_dir}")
    static_dir = None

app = Flask(__name__, 
           template_folder=template_dir,
           static_folder=static_dir)

# Configure app
app.secret_key = 'test-secret-key-for-mock-server'
app.config['TESTING'] = True

# Global state for mock server
chatters = []
chatlines = []
reviews = []


def id_generator(size=6, chars=None):
    """Generate random IDs for testing"""
    if chars is None:
        chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
    return ''.join(random.choice(chars) for i in range(size))


def get_random_color():
    """Get a random color for testing"""
    colors = ["red", "blue", "green", "orange", "purple", "brown", "pink", "gray", "olive", "cyan"]
    return random.choice(colors)


# Import email system with fallback for testing
class InMemoryFallbackEmailStorage:
    """In-memory email storage fallback for mock server tests."""

    def __init__(self):
        self.inboxes = {}

    def create_user_inbox(self, user_id):
        """Ensure an inbox exists for user_id and return it."""
        if user_id not in self.inboxes:
            self.inboxes[user_id] = []
        return self.inboxes[user_id]


class InMemoryFallbackBurnerManager:
    """In-memory burner manager used when email_system is unavailable."""

    def __init__(self, default_domain="example.com", default_hours_valid=24):
        self.default_domain = default_domain
        self.default_hours_valid = default_hours_valid
        self._burners = {}
        self._user_index = {}

    def generate_burner_email(self, user_id, domain=None, hours_valid=None):
        """Create and track a burner address with expiration metadata."""
        self.cleanup_expired()
        domain = domain or self.default_domain
        hours_valid = hours_valid or self.default_hours_valid

        base = ''.join(ch for ch in str(user_id).lower() if ch.isalnum())[:12] or "user"
        suffix = id_generator(size=8, chars=string.ascii_lowercase + string.digits)
        burner_email = f"{base}.{suffix}@{domain}"

        created_at = datetime.datetime.now()
        expires_at = created_at + datetime.timedelta(hours=hours_valid)
        self._burners[burner_email] = {
            "email": burner_email,
            "user_id": user_id,
            "created_at": created_at,
            "expires_at": expires_at,
        }
        self._user_index.setdefault(user_id, set()).add(burner_email)
        return burner_email

    def rotate_burner(self, user_id, old_email=None, domain=None, hours_valid=None):
        """Expire an existing burner and issue a replacement."""
        if old_email and self.get_user_for_burner(old_email) == user_id:
            self.expire_burner(old_email)
        return self.generate_burner_email(user_id, domain=domain, hours_valid=hours_valid)

    def get_user_burners(self, user_id):
        """Return active burner metadata for a user."""
        self.cleanup_expired()
        burners = []
        for email_addr in sorted(self._user_index.get(user_id, set())):
            data = self._burners.get(email_addr)
            if data:
                burners.append({
                    "email": data["email"],
                    "created_at": data["created_at"],
                    "expires_at": data["expires_at"],
                    "is_expired": False,
                })
        return burners

    def get_user_for_burner(self, email_addr):
        """Resolve burner ownership if the burner is still active."""
        self.cleanup_expired()
        data = self._burners.get(email_addr)
        return data["user_id"] if data else None

    def expire_burner(self, email_addr):
        """Expire a burner email immediately."""
        data = self._burners.pop(email_addr, None)
        if not data:
            return False

        user_id = data["user_id"]
        user_emails = self._user_index.get(user_id)
        if user_emails is not None:
            user_emails.discard(email_addr)
            if not user_emails:
                self._user_index.pop(user_id, None)
        return True

    def cleanup_expired(self):
        """Remove burners that have reached expiration."""
        now = datetime.datetime.now()
        expired = [
            email_addr
            for email_addr, data in self._burners.items()
            if data["expires_at"] <= now
        ]
        for email_addr in expired:
            self.expire_burner(email_addr)


def create_fallback_email_components():
    """Create fallback email storage + burner manager pair."""
    return InMemoryFallbackEmailStorage(), InMemoryFallbackBurnerManager()


try:
    from email_system import email_storage, burner_manager
except ImportError as e:
    print(f"Warning: Could not import email_system: {e}")
    email_storage, burner_manager = create_fallback_email_components()


# Add security headers
@app.after_request
def remove_headers(response):
    # Strip framework-identifying headers and avoid version leakage
    response.headers.pop("Server", None)
    response.headers["Server"] = "OpSecChat"
    response.headers["Date"] = ""
    return response


@app.route('/', methods=["GET"])
def index():
    return ('', 200)


@app.route('/health', methods=["GET"])
def health_check():
    """Health check endpoint for Playwright webServer"""
    from flask import jsonify
    return jsonify({
        'status': 'ok',
        'server': 'mock-opsechat',
        'timestamp': datetime.datetime.now().isoformat(),
        'config': {
            'hostname': app.config.get('hostname'),
            'path': app.config.get('path')
        }
    }), 200


def main():
    """Main entry point for mock server"""
    # Set up mock configuration
    app.config["hostname"] = "localhost"
    app.config["path"] = "test-path-12345"
    
    # Register mock routes
    create_mock_routes(app, chatters, chatlines, reviews, id_generator, get_random_color)
    
    # Register review routes if available
    try:
        from review_routes import register_review_routes
        
        def add_review(user_id, rating, review_text):
            review = {
                "id": id_generator(size=16),
                "user_id": user_id,
                "rating": int(rating),
                "text": review_text.strip(),
                "timestamp": datetime.datetime.now()
            }
            reviews.append(review)
            return review["id"]
        
        def get_reviews():
            return reviews
        
        def get_review_stats():
            if not reviews:
                return {"total": 0, "average_rating": 0, "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}}
            
            total = len(reviews)
            total_rating = sum(review["rating"] for review in reviews)
            average_rating = round(total_rating / total, 1)
            
            rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for review in reviews:
                rating_distribution[review["rating"]] += 1
            
            return {"total": total, "average_rating": average_rating, "rating_distribution": rating_distribution}
        
        register_review_routes(app, id_generator, get_random_color, add_review, get_reviews, get_review_stats)
    except ImportError as e:
        print(f"Warning: Could not import review_routes: {e}")
    
    print("Mock server starting on http://127.0.0.1:5001")
    print(f"Test path: http://127.0.0.1:5001/{app.config['path']}")
    
    try:
        app.run(host='127.0.0.1', port=5001, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nMock server stopped")
    except Exception as e:
        print(f"Mock server error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    print("=" * 50)
    print("Starting mock server for testing...")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Parent directory: {parent_dir}")
    print(f"Template directory: {template_dir}")
    print(f"Static directory: {static_dir}")
    if template_dir:
        print(f"Template directory exists: {os.path.exists(template_dir)}")
    if static_dir:
        print(f"Static directory exists: {os.path.exists(static_dir)}")
    print(f"Test URL: http://127.0.0.1:5001/test-path-12345")
    print(f"Health check URL: http://127.0.0.1:5001/health")
    print("=" * 50)
    
    # Validate critical directories
    if template_dir and not os.path.exists(template_dir):
        print(f"WARNING: Template directory not found: {template_dir}")
        print("Server may not render templates correctly")
    
    if static_dir and not os.path.exists(static_dir):
        print(f"WARNING: Static directory not found: {static_dir}")
        print("Static files may not be served")
    
    # Start the main server
    main()
