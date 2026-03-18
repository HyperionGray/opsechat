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
from typing import Any, Dict, List, Optional

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


class InMemoryMockEmailStorage:
    """Lightweight in-memory inbox storage used when email_system is unavailable."""

    def __init__(self):
        self.inboxes: Dict[str, List[Dict[str, Any]]] = {}

    def create_user_inbox(self, user_id: str):
        self.inboxes.setdefault(user_id, [])

    def add_email(self, user_id: str, email: Dict[str, Any]):
        self.create_user_inbox(user_id)
        email_copy = dict(email)
        email_copy.setdefault("timestamp", datetime.datetime.now())
        self.inboxes[user_id].append(email_copy)

    def get_emails(self, user_id: str) -> List[Dict[str, Any]]:
        return list(self.inboxes.get(user_id, []))


class InMemoryMockBurnerManager:
    """Simple burner manager with expiration support for mock/test fallback paths."""

    def __init__(self, domain: str = "example.com", hours_valid: int = 24):
        self.domain = domain
        self.hours_valid = hours_valid
        self.burners: Dict[str, Dict[str, Any]] = {}
        self.user_burners: Dict[str, List[str]] = {}

    def cleanup_expired(self):
        now = datetime.datetime.now()
        expired = [
            email for email, meta in self.burners.items()
            if meta["expires_at"] <= now
        ]
        for email in expired:
            user_id = self.burners[email]["user_id"]
            del self.burners[email]
            if user_id in self.user_burners:
                self.user_burners[user_id] = [
                    burner for burner in self.user_burners[user_id] if burner != email
                ]

    def generate_burner_email(self, user_id: str):
        self.cleanup_expired()
        local_part = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))
        email = f"{local_part}@{self.domain}"
        now = datetime.datetime.now()
        self.burners[email] = {
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + datetime.timedelta(hours=self.hours_valid)
        }
        self.user_burners.setdefault(user_id, []).append(email)
        return email

    def rotate_burner(self, user_id: str, old_email: Optional[str] = None):
        if old_email:
            self.expire_burner(old_email)
        return self.generate_burner_email(user_id)

    def get_user_burners(self, user_id: str):
        self.cleanup_expired()
        result = []
        for email in self.user_burners.get(user_id, []):
            meta = self.burners.get(email)
            if meta:
                result.append(
                    {
                        "email": email,
                        "created_at": meta["created_at"],
                        "expires_at": meta["expires_at"]
                    }
                )
        return result

    def get_user_for_burner(self, email: str):
        self.cleanup_expired()
        meta = self.burners.get(email)
        if not meta:
            return None
        return meta["user_id"]

    def expire_burner(self, email: str):
        if email not in self.burners:
            return False
        user_id = self.burners[email]["user_id"]
        del self.burners[email]
        if user_id in self.user_burners:
            self.user_burners[user_id] = [
                burner for burner in self.user_burners[user_id] if burner != email
            ]
        return True


# Import email system with fallback for testing
try:
    from email_system import email_storage, burner_manager
except ImportError as e:
    print(f"Warning: Could not import email_system: {e}")
    email_storage = InMemoryMockEmailStorage()
    burner_manager = InMemoryMockBurnerManager()


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
