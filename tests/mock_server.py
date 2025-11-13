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

app = Flask(__name__)
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

if __name__ == '__main__':
    print("Starting mock server for testing...")
    app.run(debug=False, port=5000, threaded=True)
