"""
Chat Routes Blueprint for opsechat

This module contains all chat-related routes extracted from runserver.py
to improve code organization and maintainability.
"""

import re
import datetime
from flask import Blueprint, render_template, request, session, redirect, jsonify, current_app
from utils import id_generator, get_random_color, check_older_than
import state_manager

# Create blueprint
chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/<string:url_addition>/script', methods=["GET"])
def drop(url_addition):
    """Chat interface with script enabled"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        state_manager.get_chatters().append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        return render_template("drop.html",
                               hostname=current_app.config["hostname"],
                               path=current_app.config["path"],
                               script_enabled=True)


@chat_bp.route('/<string:url_addition>', methods=["GET"])
def drop_landing(url_addition):
    """Landing page with auto-redirect"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        state_manager.get_chatters().append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        return render_template("landing_auto.html",
                               hostname=current_app.config["hostname"],
                               path=current_app.config["path"])


@chat_bp.route('/<string:url_addition>/autolanding', methods=["GET"])
def drop_landing_auto(url_addition):
    """Auto-landing page"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        state_manager.get_chatters().append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        return render_template("landing_auto.html",
                               hostname=current_app.config["hostname"],
                               path=current_app.config["path"])

    
@chat_bp.route('/<string:url_addition>/yesscript', methods=["GET"])
def drop_yes(url_addition):
    """Chat interface with JavaScript enabled"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        state_manager.get_chatters().append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        return render_template("drop.html",
                               hostname=current_app.config["hostname"],
                               path=current_app.config["path"],
                               script_enabled=True)


@chat_bp.route('/<string:url_addition>/noscript', methods=["GET"])
def drop_noscript(url_addition):
    """Chat interface without JavaScript"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        state_manager.get_chatters().append(session["_id"])
        session["color"] = get_random_color()

    if request.method == "GET":
        return render_template("drop.html",
                               hostname=current_app.config["hostname"],
                               path=current_app.config["path"],
                               script_enabled=False)


@chat_bp.route('/<string:url_addition>/chats', methods=["GET", "POST"])
def chat_messages(url_addition):
    """Handle chat messages (no-script version)"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    chatlines = state_manager.get_chatlines()
    chatters = state_manager.get_chatters()

    # Clean up old messages (older than 3 minutes)
    to_delete = []
    c = 0
    if chatlines:
        for chatline_dic in chatlines:
            if check_older_than(chatline_dic):
                to_delete.append(c)
            c += 1

    for _del in reversed(to_delete):
        chatlines.pop(_del)

    if request.method == "POST":
        if request.form["dropdata"].strip():
            chat = {}
            chat["msg"] = request.form["dropdata"].strip()
            # Don't sanitize PGP messages, only sanitize regular messages
            if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
                chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
            chat["timestamp"] = datetime.datetime.now()
            chat["username"] = session["_id"]
            chat["color"] = session["color"]
            chats = [chat]
            chatlines = chatlines + chats
            chatlines = chatlines[-13:]  # Keep only last 13 messages
            state_manager.set_chatlines(chatlines)

        return redirect(current_app.config["path"], code=302)
    
    return render_template("chats.html",
                           chatlines=chatlines, 
                           num_people=len(chatters))


@chat_bp.route('/<string:url_addition>/chatsjs', methods=["GET", "POST"])
def chat_messages_js(url_addition):
    """Handle chat messages (JavaScript version - returns JSON)"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    chatlines = state_manager.get_chatlines()
    chatters = state_manager.get_chatters()

    # Clean up old messages (older than 3 minutes)
    to_delete = []
    c = 0
    if chatlines:
        for chatline_dic in chatlines:
            if check_older_than(chatline_dic):
                to_delete.append(c)
            c += 1

    for _del in reversed(to_delete):
        chatlines.pop(_del)

    if request.method == "POST":
        if request.form["dropdata"].strip():
            chat = {}
            chat["msg"] = request.form["dropdata"].strip()
            # Don't sanitize PGP messages, only sanitize regular messages
            if "-----BEGIN PGP MESSAGE-----" not in chat["msg"]:
                chat["msg"] = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', chat["msg"])
            chat["timestamp"] = datetime.datetime.now()
            chat["username"] = session["_id"]
            chat["color"] = session["color"]
            chat["num_people"] = len(chatters)
            chats = [chat]
            chatlines = chatlines + chats
            chatlines = chatlines[-13:]  # Keep only last 13 messages
            state_manager.set_chatlines(chatlines)

    return jsonify(chatlines)