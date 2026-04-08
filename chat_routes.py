"""
Chat system routes for opsechat.

This module backs the legacy secret-path chat experience used throughout the
documentation and a large part of the existing Playwright coverage.  The
templates already present in ``templates/`` are built around ``/chats`` and
``/chatsjs`` endpoints, so the route layer intentionally preserves those URLs
and provides compatibility aliases for newer ``/messages`` and
``/messages.json`` paths.
"""

import re
import datetime
from flask import render_template, request, session, jsonify, redirect, url_for
from utils import sanitize_emojis, filter_to_ascii


def register_chat_routes(app, chatlines, chatters, id_generator, get_random_color,
                        check_older_than, process_chat):
    """Register all chat-related routes with the Flask app"""
    # Security headers are applied globally via @app.after_request in app_factory.

    def _ensure_session():
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()

    def _normalize_color(color_value):
        """Return a CSS-friendly color string for legacy templates."""
        if isinstance(color_value, (list, tuple)) and len(color_value) == 3:
            return ",".join(str(channel) for channel in color_value)
        return color_value

    def _store_legacy_message(message_text):
        message = {
            "msg": message_text,
            "user_id": session["_id"],
            "username": session["_id"],
            "color": _normalize_color(session["color"]),
            "timestamp": datetime.datetime.now(),
            "num_people": len(chatters),
        }
        chatlines.append(message)

        chatter_ids = {
            chatter["user_id"] if isinstance(chatter, dict) else chatter
            for chatter in chatters
        }
        if session["_id"] not in chatter_ids:
            chatters.append({
                "user_id": session["_id"],
                "color": _normalize_color(session["color"]),
                "timestamp": datetime.datetime.now(),
            })

        # Keep the legacy room bounded.
        if len(chatlines) > 13:
            del chatlines[:-13]

    def _sanitize_legacy_message(message_text):
        message_text = filter_to_ascii(message_text)
        message_text = sanitize_emojis(message_text)

        # Preserve armored PGP payloads exactly; sanitize everything else.
        if "-----BEGIN PGP MESSAGE-----" not in message_text:
            message_text = re.sub(r'([^\s\w\.\?\!\:\)\(\*])+', '', message_text)

        return message_text.strip()

    def _cleanup_messages():
        to_remove = [msg for msg in chatlines if check_older_than(msg)]
        for msg in to_remove:
            chatlines.remove(msg)

    def _processed_chatlines():
        _cleanup_messages()
        processed_messages = []
        for msg in chatlines:
            processed_messages.extend(process_chat(msg))
        return processed_messages

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

        _ensure_session()

        return render_template("drop.html",
                              hostname=app.config["hostname"], 
                              path=app.config["path"], 
                              script_enabled=True)

    @app.route('/<string:url_addition>/noscript')
    def drop_noscript(url_addition):
        """No-JavaScript chat interface"""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session()

        return render_template("drop.noscript.html",
                              hostname=app.config["hostname"], 
                              path=app.config["path"], 
                              script_enabled=False)

    @app.route('/<string:url_addition>/chats', methods=["GET", "POST"])
    def chat_lines(url_addition):
        """Legacy no-JavaScript chat iframe endpoint."""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session()

        if request.method == "POST":
            message_text = request.form.get("dropdata", "").strip()
            if message_text:
                _store_legacy_message(_sanitize_legacy_message(message_text))
            return redirect(url_for("drop", url_addition=url_addition))

        processed_messages = _processed_chatlines()
        return render_template(
            "chats.html",
            chatlines=processed_messages,
            num_people=len(chatters),
        )

    @app.route('/<string:url_addition>/chatsjs', methods=["GET", "POST"])
    def chat_lines_json(url_addition):
        """Legacy JavaScript polling endpoint."""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session()

        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            message_text = payload.get("message", "").strip()
            if not message_text:
                message_text = request.form.get("dropdata", "").strip()

            if message_text:
                _store_legacy_message(_sanitize_legacy_message(message_text))

        processed_messages = _processed_chatlines()
        return jsonify(processed_messages)

    @app.route('/<string:url_addition>/messages', methods=["GET", "POST"])
    def chat_messages(url_addition):
        """Compatibility alias for legacy chat iframe posting."""
        if request.method == "POST":
            if url_addition != app.config["path"]:
                return ('', 404)

            message_text = request.form.get("message", "").strip()
            if message_text:
                _ensure_session()
                _store_legacy_message(_sanitize_legacy_message(message_text))
            return redirect(url_for("chat_messages", url_addition=url_addition))

        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session()
        processed_messages = _processed_chatlines()
        return render_template(
            "chats.html",
            chatlines=processed_messages,
            num_people=len(chatters),
        )

    @app.route('/<string:url_addition>/messages.json', methods=["GET", "POST"])
    def chat_messages_json(url_addition):
        """Compatibility JSON endpoint used by newer tests."""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session()

        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            message_text = data.get("message", "").strip()
            if message_text:
                _store_legacy_message(_sanitize_legacy_message(message_text))

        processed_messages = _processed_chatlines()
        return jsonify({
            "messages": processed_messages,
            "user_id": session["_id"],
            "user_color": _normalize_color(session["color"]),
        })
