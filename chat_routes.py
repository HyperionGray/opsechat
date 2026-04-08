"""
Chat system routes for opsechat

This module contains Flask routes for the core chat functionality including:
- Chat message handling
- User session management
- Message cleanup and processing
- JavaScript and no-JavaScript chat interfaces
"""

import re
import datetime
from flask import render_template, request, session, jsonify
from utils import sanitize_emojis, filter_to_ascii


def register_chat_routes(app, chatlines, chatters, id_generator, get_random_color,
                        check_older_than, process_chat):
    """Register all chat-related routes with the Flask app"""
    # Security headers are applied globally via @app.after_request in app_factory.

    color_map = {
        "red": [255, 85, 85],
        "blue": [85, 145, 255],
        "green": [80, 200, 120],
        "orange": [255, 165, 0],
        "purple": [180, 110, 255],
        "brown": [160, 110, 70],
        "pink": [255, 105, 180],
        "gray": [170, 170, 170],
        "olive": [128, 128, 0],
        "cyan": [0, 200, 200],
    }

    def normalize_color(color_value):
        """Normalize any stored color value to an RGB list."""
        if isinstance(color_value, (list, tuple)) and len(color_value) == 3:
            try:
                return [int(color_value[0]), int(color_value[1]), int(color_value[2])]
            except (TypeError, ValueError):
                return [200, 200, 200]
        if isinstance(color_value, str):
            return color_map.get(color_value.lower(), [200, 200, 200])
        return [200, 200, 200]

    def ensure_session_user():
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = normalize_color(get_random_color())
        else:
            session["color"] = normalize_color(session.get("color"))

        if session["_id"] not in chatters:
            chatters.append(session["_id"])

    @app.route('/<string:url_addition>')
    def drop(url_addition):
        """Main chat landing page"""
        if url_addition != app.config["path"]:
            return ('', 404)
        return render_template("landing.html", 
                              hostname=app.config["hostname"], 
                              path=app.config["path"])

    @app.route('/<string:url_addition>/landing')
    def drop_landing(url_addition):
        """Chat landing page with explicit landing route"""
        if url_addition != app.config["path"]:
            return ('', 404)
        return render_template("landing.html", 
                              hostname=app.config["hostname"], 
                              path=app.config["path"])

    @app.route('/<string:url_addition>/landing/auto')
    def drop_landing_auto(url_addition):
        """Auto-redirect landing page for JavaScript detection"""
        if url_addition != app.config["path"]:
            return ('', 404)
        return render_template("landing_auto.html", 
                              hostname=app.config["hostname"], 
                              path=app.config["path"])

    @app.route('/<string:url_addition>/yesscript')
    def drop_yes(url_addition):
        """JavaScript-enabled chat interface"""
        if url_addition != app.config["path"]:
            return ('', 404)

        ensure_session_user()

        return render_template("drop.html",
                              hostname=app.config["hostname"], 
                              path=app.config["path"], 
                              script_enabled=True)

    @app.route('/<string:url_addition>/noscript')
    def drop_noscript(url_addition):
        """No-JavaScript chat interface"""
        if url_addition != app.config["path"]:
            return ('', 404)

        ensure_session_user()

        return render_template("drop.html",
                              hostname=app.config["hostname"], 
                              path=app.config["path"], 
                              script_enabled=False)

    @app.route('/<string:url_addition>/chats', methods=["GET", "POST"])
    @app.route('/<string:url_addition>/messages', methods=["GET", "POST"])
    def chat_messages(url_addition):
        """Handle chat messages for no-JavaScript interface and compatibility."""
        if url_addition != app.config["path"]:
            return ('', 404)

        ensure_session_user()

        if request.method == "POST":
            # Process new message
            message_text = request.form.get("dropdata", "").strip()
            if not message_text:
                message_text = request.form.get("message", "").strip()
            if message_text:
                # Filter to ASCII and remove emojis
                message_text = filter_to_ascii(message_text)
                message_text = sanitize_emojis(message_text)
                # Sanitize message
                message_text = re.sub(r'[<>&"\']', '', message_text)

                if "-----BEGIN PGP MESSAGE-----" not in message_text:
                    message_text = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', message_text)

                chatlines.append({
                    "msg": message_text,
                    "username": session["_id"],
                    "color": session["color"],
                    "timestamp": datetime.datetime.now(),
                })
                # Keep memory bounded.
                if len(chatlines) > 250:
                    del chatlines[:-250]

        # Clean up old messages (modify in place to preserve reference)
        to_remove = [msg for msg in chatlines if check_older_than(msg)]
        for msg in to_remove:
            chatlines.remove(msg)

        # Process messages for display (flatten wrapped outputs).
        processed_messages = []
        for msg in chatlines:
            processed_messages.extend(process_chat(msg))

        return render_template("chats.html",
                              chatlines=processed_messages,
                              num_people=len(chatters))

    @app.route('/<string:url_addition>/chatsjs', methods=["GET", "POST"])
    @app.route('/<string:url_addition>/messages.json', methods=["GET", "POST"])
    def chat_messages_js(url_addition):
        """Handle chat messages for JavaScript interface and compatibility."""
        if url_addition != app.config["path"]:
            return ('', 404)

        ensure_session_user()

        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            message_text = (data.get("message") or "").strip()
            if not message_text:
                message_text = request.form.get("dropdata", "").strip()
            if not message_text:
                message_text = request.form.get("message", "").strip()
            if message_text:
                message_text = filter_to_ascii(message_text)
                message_text = sanitize_emojis(message_text)
                message_text = re.sub(r'[<>&"\']', '', message_text)
                if "-----BEGIN PGP MESSAGE-----" not in message_text:
                    message_text = re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', message_text)

                chatlines.append({
                    "msg": message_text,
                    "username": session["_id"],
                    "color": session["color"],
                    "timestamp": datetime.datetime.now(),
                })
                if len(chatlines) > 250:
                    del chatlines[:-250]

        # Clean up old messages (modify in place to preserve reference)
        to_remove = [msg for msg in chatlines if check_older_than(msg)]
        for msg in to_remove:
            chatlines.remove(msg)

        processed_messages = []
        for msg in chatlines:
            processed_messages.extend(process_chat(msg))

        payload = []
        for msg in processed_messages:
            json_msg = dict(msg)
            if isinstance(json_msg.get("timestamp"), datetime.datetime):
                json_msg["timestamp"] = json_msg["timestamp"].isoformat()
            json_msg["color"] = normalize_color(json_msg.get("color"))
            json_msg["num_people"] = len(chatters)
            payload.append(json_msg)

        if request.path.endswith("/messages.json"):
            return jsonify({
                "messages": payload,
                "user_id": session["_id"],
                "user_color": session["color"],
            })

        return jsonify(payload)
