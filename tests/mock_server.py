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
from email_system import email_storage, burner_manager

# Create Flask app with the correct template directory
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')
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
    
    return render_template("landing_auto.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"])

@app.route('/<string:url_addition>/script', methods=["GET"])
def drop_script(url_addition):
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()
    
    return render_template("drop.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"])

@app.route('/<string:url_addition>/noscript', methods=["GET"])
def drop_noscript(url_addition):
    if "_id" not in session:
        session["_id"] = id_generator()
        chatters.append(session["_id"])
        session["color"] = get_random_color()
    
    return render_template("drop.noscript.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"])

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
    
    return render_template("chats.html",
                          chatlines=chatlines,
                          num_people=len(chatters))

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
    
    return render_template("email_burner.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          active_burners=active_burners,
                          script_enabled=False)

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
    
    return render_template("email_burner.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          active_burners=active_burners,
                          script_enabled=True)

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
    print(f"Test URL: http://localhost:5001/{app.config['path']}/email/burner")
    app.run(debug=False, host='127.0.0.1', port=5001, threaded=True)
