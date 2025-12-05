#!/usr/bin/env python3
"""
Mock server for testing opsechat without requiring Tor
This server simulates the basic Flask routes for testing purposes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, session, request, jsonify, redirect
import string
import random
import datetime
import re

# Import email system
try:
    from email_system import email_storage, burner_manager
except ImportError as e:
    print(f"Warning: Could not import email_system: {e}")
    # Create mock objects for testing
    class MockEmailStorage:
        def create_user_inbox(self, user_id): pass
    class MockBurnerManager:
        def cleanup_expired(self): pass
        def generate_burner_email(self, user_id): return f"test{user_id}@example.com"
        def rotate_burner(self, user_id, old_email): return f"test{user_id}@example.com"
        def get_user_burners(self, user_id): return []
        def get_user_for_burner(self, email): return None
        def expire_burner(self, email): pass
    
    email_storage = MockEmailStorage()
    burner_manager = MockBurnerManager()

# Create Flask app with the correct template directory
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')

# Verify directories exist
if not os.path.exists(template_dir):
    print(f"Warning: Template directory not found: {template_dir}")
if not os.path.exists(static_dir):
    print(f"Warning: Static directory not found: {static_dir}")

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = 'test-secret-key-for-mock-server'

# Mock configuration
app.config['hostname'] = 'mock.onion'
app.config['path'] = 'test-path-12345'

chatters = []
chatlines = []

def id_generator(size=6, chars=string.ascii_uppercase + string.digits + string.ascii_lowercase):
    return ''.join(random.choice(chars) for i in range(size))

def get_random_color():
    r = lambda: random.randint(0, 128)
    return (r(), r(), r())

# Remove headers that can be used to fingerprint this server
@app.after_request
def remove_headers(response):
    response.headers["Server"] = ""
    response.headers["Date"] = ""
    return response

@app.route('/', methods=["GET"])
def index():
    return ('', 200)

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
    print("Starting mock server for testing...")
    print(f"Template directory: {template_dir}")
    print(f"Static directory: {static_dir}")
    print(f"Test URL: http://127.0.0.1:5001/{app.config['path']}")
    print(f"Health check URL: http://127.0.0.1:5001/")
    
    try:
        app.run(debug=False, host='127.0.0.1', port=5001, threaded=True)
    except Exception as e:
        print(f"Error starting mock server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
