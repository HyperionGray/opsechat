#!/usr/bin/env python3
"""
Mock server for testing opsechat without requiring Tor
This server simulates the basic Flask routes for testing purposes
"""

import sys
import os

# Add the parent directory to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from flask import Flask, render_template, session, request, jsonify, redirect
import string
import random
import datetime
import re

# Import email system with better error handling
email_storage = None
burner_manager = None

try:
    from email_system import email_storage, burner_manager
    print("Successfully imported email_system")
except ImportError as e:
    print(f"Warning: Could not import email_system: {e}")
    print("Using mock objects for testing")
    
    # Create mock objects for testing
    class MockEmailStorage:
        def create_user_inbox(self, user_id): 
            print(f"Mock: Creating inbox for user {user_id}")
        def get_emails(self, user_id): 
            return []
        def add_email(self, user_id, email_data): 
            print(f"Mock: Adding email for user {user_id}")
        def get_email(self, user_id, email_id): 
            return None
        def update_email_raw(self, user_id, email_id, raw_content): 
            print(f"Mock: Updating email {email_id} for user {user_id}")
        def delete_email(self, user_id, email_id): 
            return True
    
    class MockBurnerManager:
        def cleanup_expired(self): 
            print("Mock: Cleaning up expired burners")
        def generate_burner_email(self, user_id): 
            email = f"test{user_id}@example.com"
            print(f"Mock: Generated burner email {email}")
            return {"email": email, "expires_at": datetime.datetime.now() + datetime.timedelta(hours=1)}
        def rotate_burner(self, user_id, old_email): 
            email = f"test{user_id}@example.com"
            print(f"Mock: Rotated burner email to {email}")
            return {"email": email, "expires_at": datetime.datetime.now() + datetime.timedelta(hours=1)}
        def get_user_burners(self, user_id): 
            return []
        def get_user_for_burner(self, email): 
            return None
        def expire_burner_email(self, user_id, email): 
            print(f"Mock: Expiring burner {email} for user {user_id}")
            return True
        def expire_burner(self, email): 
            print(f"Mock: Expiring burner {email}")
    
    email_storage = MockEmailStorage()
    burner_manager = MockBurnerManager()

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
app.secret_key = 'test-secret-key-for-mock-server'

# Mock configuration
app.config['hostname'] = 'mock.onion'
app.config['path'] = 'test-path-12345'

chatters = []
chatlines = []

# Review system storage
reviews = []

def id_generator(size=6, chars=string.ascii_uppercase + string.digits + string.ascii_lowercase):
    return ''.join(random.choice(chars) for i in range(size))

def get_random_color():
    r = lambda: random.randint(0, 128)
    return (r(), r(), r())

def check_review_older_than(review_dic, secs_to_live=86400):  # 24 hours
    """Check if a review is older than specified seconds (default 24 hours)"""
    now = datetime.datetime.now()
    timestamp = review_dic["timestamp"]
    diff = now - timestamp
    secs = diff.total_seconds()
    
    if secs >= secs_to_live:
        return True
    return False

def cleanup_old_reviews():
    """Remove reviews older than 24 hours to prevent memory bloat"""
    global reviews
    to_delete = []
    
    for i, review in enumerate(reviews):
        if check_review_older_than(review):
            to_delete.append(i)
    
    # Remove in reverse order to maintain indices
    for i in reversed(to_delete):
        reviews.pop(i)

def add_review(user_id, rating, review_text):
    """Add a new review to the global reviews list"""
    global reviews
    
    # Cleanup old reviews first
    cleanup_old_reviews()
    
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
    """Get all current reviews, cleanup old ones first"""
    cleanup_old_reviews()
    return reviews

def get_review_stats():
    """Get review statistics"""
    cleanup_old_reviews()
    
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

# Register review routes with the Flask app
try:
    from review_routes import register_review_routes
    register_review_routes(app, id_generator, get_random_color, add_review, get_reviews, get_review_stats)
    print("Successfully registered review routes")
except ImportError as e:
    print(f"Warning: Could not import review_routes: {e}")
    print("Review functionality will not be available")
except Exception as e:
    print(f"Warning: Could not register review routes: {e}")
    print("Review functionality will not be available")

# Remove headers that can be used to fingerprint this server
@app.after_request
def remove_headers(response):
    response.headers["Server"] = ""
    response.headers["Date"] = ""
    return response

@app.route('/', methods=["GET"])
def index():
    return ('', 200)

@app.route('/health', methods=["GET"])
def health_check():
    """Health check endpoint for testing"""
    return jsonify({
        "status": "ok",
        "server": "mock",
        "timestamp": datetime.datetime.now().isoformat(),
        "config": {
            "hostname": app.config["hostname"],
            "path": app.config["path"]
        }
    }), 200

@app.route('/<string:url_addition>', methods=["GET"])
def drop_landing(url_addition):
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()
    
    try:
        return render_template("landing_auto.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"])
    except Exception as e:
        print(f"Template rendering error: {e}")
        # Fallback to simple HTML response
        return f'''
        <html>
        <head><title>Opsechat Test</title></head>
        <body>
        <h1>Opsechat Test Server</h1>
        <p>Hostname: {app.config["hostname"]}</p>
        <p>Path: {app.config["path"]}</p>
        <p><a href="/{app.config["path"]}/script">Script Version</a></p>
        <p><a href="/{app.config["path"]}/noscript">NoScript Version</a></p>
        </body>
        </html>
        ''', 200

@app.route('/<string:url_addition>/script', methods=["GET"])
def drop_script(url_addition):
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()
    
    try:
        return render_template("drop.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"])
    except Exception as e:
        print(f"Template rendering error in /script: {e}")
        return f'''
        <html>
        <head><title>Opsechat Script Version</title></head>
        <body>
        <h1>Opsechat Script Version</h1>
        <p>JavaScript enabled version</p>
        <p><a href="/{app.config["path"]}/chats">View Chats</a></p>
        </body>
        </html>
        ''', 200

@app.route('/<string:url_addition>/noscript', methods=["GET"])
def drop_noscript(url_addition):
    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()
    
    try:
        return render_template("drop.noscript.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"])
    except Exception as e:
        print(f"Template rendering error in /noscript: {e}")
        return f'''
        <html>
        <head><title>Opsechat NoScript Version</title></head>
        <body>
        <h1>Opsechat NoScript Version</h1>
        <p>JavaScript disabled version</p>
        <p><a href="/{app.config["path"]}/chats">View Chats</a></p>
        </body>
        </html>
        ''', 200

@app.route('/<string:url_addition>/chats', methods=["GET", "POST"])
def chat_messages(url_addition):
    global chatlines
    
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if request.method == "POST":
        if request.form.get("dropdata", "").strip():
            chat = {}
            chat["msg"] = request.form["dropdata"].strip()
            if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
                chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
            chat["timestamp"] = datetime.datetime.now()
            chat["username"] = session.get("_id", "anonymous")
            chat["color"] = session.get("color", (128, 128, 128))
            chatlines.append(chat)
            chatlines = chatlines[-13:]
        
        return redirect(app.config["path"], code=302)
    
    try:
        return render_template("chats.html",
                              chatlines=chatlines,
                              num_people=len(chatters))
    except Exception as e:
        print(f"Template rendering error in /chats: {e}")
        # Fallback to simple HTML response
        chat_html = ""
        for chat in chatlines[-10:]:  # Show last 10 messages
            chat_html += f"<p><strong>{chat.get('username', 'anonymous')}</strong>: {chat.get('msg', '')}</p>"
        
        return f'''
        <html>
        <head><title>Opsechat Chats</title></head>
        <body>
        <h1>Chat Messages</h1>
        <div>{chat_html}</div>
        <p>People online: {len(chatters)}</p>
        <form method="post">
        <input type="text" name="dropdata" placeholder="Enter message">
        <input type="submit" value="Send">
        </form>
        </body>
        </html>
        ''', 200

@app.route('/<string:url_addition>/chatsjs', methods=["GET", "POST"])
def chat_messages_js(url_addition):
    global chatlines
    
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if request.method == "POST":
        if request.form.get("dropdata", "").strip():
            chat = {}
            chat["msg"] = request.form["dropdata"].strip()
            if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
                chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
            chat["timestamp"] = datetime.datetime.now()
            chat["username"] = session.get("_id", "anonymous")
            chat["color"] = session.get("color", (128, 128, 128))
            chat["num_people"] = len(chatters)
            chatlines.append(chat)
            chatlines = chatlines[-13:]
    
    return jsonify(chatlines)

# Email routes
@app.route('/<string:url_addition>/email/burner', methods=["GET", "POST"])
def email_burner(url_addition):
    """Generate burner email address - Modern rotating interface"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    # Cleanup expired burners
    burner_manager.cleanup_expired()
    
    if request.method == "POST":
        action = request.form.get("action", "generate")
        
        if action == "generate":
            burner_email = burner_manager.generate_burner_email(session["_id"])
            email_storage.create_user_inbox(session["_id"])
        elif action == "rotate":
            old_email = request.form.get("old_email")
            burner_email = burner_manager.rotate_burner(session["_id"], old_email)
            email_storage.create_user_inbox(session["_id"])
    
    # Get all active burners for this user
    active_burners = burner_manager.get_user_burners(session["_id"])
    
    try:
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              active_burners=active_burners,
                              script_enabled=False)
    except Exception as e:
        print(f"Template rendering error in /email/burner: {e}")
        # Fallback to simple HTML response
        burner_html = ""
        for burner in active_burners:
            burner_html += f"<p>Email: {burner.get('email', 'N/A')}</p>"
        
        return f'''
        <html>
        <head><title>Burner Email</title></head>
        <body>
        <h1>Burner Email Generator</h1>
        <div>{burner_html}</div>
        <form method="post">
        <input type="hidden" name="action" value="generate">
        <input type="submit" value="Generate New Burner">
        </form>
        </body>
        </html>
        ''', 200

@app.route('/<string:url_addition>/email/burner/yesscript', methods=["GET"])
def email_burner_script(url_addition):
    """Burner email with JavaScript enabled"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    burner_manager.cleanup_expired()
    active_burners = burner_manager.get_user_burners(session["_id"])
    
    try:
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              active_burners=active_burners,
                              script_enabled=True)
    except Exception as e:
        print(f"Template rendering error in /email/burner/yesscript: {e}")
        # Fallback to simple HTML response
        burner_html = ""
        for burner in active_burners:
            burner_html += f"<p>Email: {burner.get('email', 'N/A')}</p>"
        
        return f'''
        <html>
        <head><title>Burner Email (Script Enabled)</title></head>
        <body>
        <h1>Burner Email Generator (JavaScript)</h1>
        <div>{burner_html}</div>
        <form method="post">
        <input type="hidden" name="action" value="generate">
        <input type="submit" value="Generate New Burner">
        </form>
        </body>
        </html>
        ''', 200

@app.route('/<string:url_addition>/email/burner/list', methods=["GET"])
def email_burner_list_json(url_addition):
    """Get active burners as JSON (for AJAX refresh)"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return jsonify([])
    
    burner_manager.cleanup_expired()
    active_burners = burner_manager.get_user_burners(session["_id"])
    
    return jsonify(active_burners)

@app.route('/<string:url_addition>/email/burner/expire/<string:email>', methods=["POST"])
def email_burner_expire(url_addition, email):
    """Expire a specific burner email"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    # Verify this burner belongs to the user
    burner_user = burner_manager.get_user_for_burner(email)
    if burner_user == session["_id"]:
        burner_manager.expire_burner(email)
    
    return redirect(f"/{app.config['path']}/email/burner", code=302)

if __name__ == '__main__':
    print("=" * 50)
    print("Starting mock server for testing...")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Project root: {project_root}")
    print(f"Template directory: {template_dir}")
    print(f"Static directory: {static_dir}")
    print(f"Template directory exists: {os.path.exists(template_dir)}")
    print(f"Static directory exists: {os.path.exists(static_dir)}")
    print(f"Test URL: http://127.0.0.1:5001/{app.config['path']}")
    print(f"Health check URL: http://127.0.0.1:5001/")
    print("=" * 50)
    
    # Validate critical directories
    if not os.path.exists(template_dir):
        print(f"ERROR: Template directory not found: {template_dir}")
        print("Server may not render templates correctly")
    
    if not os.path.exists(static_dir):
        print(f"WARNING: Static directory not found: {static_dir}")
        print("Static files may not be served")
    
    try:
        print("Starting Flask server...")
        app.run(debug=False, host='127.0.0.1', port=5001, threaded=True)
    except Exception as e:
        print(f"ERROR: Failed to start mock server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
