"""
HTTP Mail Routes for opsechat

Email-over-HTTP: no SMTP, no IMAP — messages are posted to in-memory mailboxes
and read back using a private read_key (default deny).

Routes registered under /<path>/mail/:
  GET  /<path>/mail                        - Main UI (create mailbox form)
  POST /<path>/mail/new                    - Create a new mailbox
  POST /<path>/mail/send                   - Send a message (address in body/form)
  POST /<path>/mail/<address>/send         - Send a message to a mailbox (no auth)
  GET  /<path>/mail/<address>/inbox        - Read inbox (requires ?key=<read_key>)
  POST /<path>/mail/<address>/delete/<id>  - Delete a message (requires read_key in form)
  POST /<path>/mail/<address>/destroy      - Delete entire mailbox (requires read_key in form)
"""

import re
from flask import render_template, request, session, jsonify, redirect, url_for
from http_mail_system import http_mail_storage, MAX_MAIL_MESSAGE_LENGTH
from utils import id_generator, get_random_color


def register_http_mail_routes(app):
    """Register HTTP mail routes with the Flask app."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_session():
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()

    def _sanitize(text: str, max_len: int) -> str:
        """Strip dangerous characters and enforce length."""
        text = re.sub(r'[<>&"\']', '', text)
        return text[:max_len]

    def _wants_json_response() -> bool:
        """Return True when client explicitly asks for JSON."""
        accept = request.headers.get("Accept", "")
        return request.is_json or "application/json" in accept

    def _send_error(message: str, status_code: int, compose_address: str = ""):
        """Return a JSON or HTML error payload based on content negotiation."""
        if _wants_json_response():
            return jsonify({"error": message}), status_code
        return render_template(
            "http_mail.html",
            path=app.config["path"],
            hostname=app.config.get("hostname", ""),
            max_message_length=MAX_MAIL_MESSAGE_LENGTH,
            error=message,
            compose_address=compose_address,
        ), status_code

    def _handle_send(url_addition: str, route_address: str = ""):
        """Send a message to a mailbox from either route-form or JSON payload."""
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        if request.is_json:
            data = request.get_json(silent=True) or {}
            address = route_address or data.get("address", "").strip()
            subject = data.get("subject", "").strip()
            body = data.get("body", "").strip()
            sender = data.get("sender", "anonymous").strip()
        else:
            address = route_address or request.form.get("_address_override", "").strip()
            subject = request.form.get("subject", "").strip()
            body = request.form.get("body", "").strip()
            sender = request.form.get("sender", "anonymous").strip()

        address = _sanitize(address, 128)
        if not address:
            return _send_error("Mailbox address is required", 400)

        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            return _send_error("Mailbox not found", 404, compose_address=address)

        if not body:
            return _send_error("Message body is required", 400, compose_address=address)

        subject = _sanitize(subject, 200) or "(no subject)"
        body = _sanitize(body, MAX_MAIL_MESSAGE_LENGTH)
        sender = _sanitize(sender, 64) or "anonymous"

        try:
            msg_id = mailbox.add_message(subject=subject, body=body, sender_handle=sender)
        except ValueError:
            return _send_error("Mailbox is no longer available", 410, compose_address=address)

        if _wants_json_response():
            return jsonify({"success": True, "msg_id": msg_id, "address": address})

        return render_template(
            "http_mail.html",
            path=app.config["path"],
            hostname=app.config.get("hostname", ""),
            max_message_length=MAX_MAIL_MESSAGE_LENGTH,
            success="Message sent.",
            compose_address=address,
        )

    # ------------------------------------------------------------------
    # Main UI — create or access mailbox
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail', methods=["GET"])
    def http_mail_index(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        return render_template("http_mail.html",
                               path=app.config["path"],
                               hostname=app.config.get("hostname", ""),
                               max_message_length=MAX_MAIL_MESSAGE_LENGTH)

    # ------------------------------------------------------------------
    # Create a new mailbox
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/new', methods=["POST"])
    def http_mail_create(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        mailbox = http_mail_storage.create_mailbox()
        # JSON response — the UI stores address + read_key locally
        return jsonify({
            "success": True,
            "address": mailbox.address,
            "read_key": mailbox.read_key,
            "send_url": f"/{url_addition}/mail/{mailbox.address}/send",
            "inbox_url": f"/{url_addition}/mail/{mailbox.address}/inbox",
        })

    # ------------------------------------------------------------------
    # Send a message to a mailbox (fallback endpoint, no JS required)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/send', methods=["POST"])
    def http_mail_send_fallback(url_addition):
        return _handle_send(url_addition)

    # ------------------------------------------------------------------
    # Send a message to a mailbox (no authentication required)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/<string:address>/send', methods=["POST"])
    def http_mail_send(url_addition, address):
        return _handle_send(url_addition, route_address=address)

    # ------------------------------------------------------------------
    # Read inbox (requires read_key)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/<string:address>/inbox', methods=["GET"])
    def http_mail_inbox(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            if _wants_json_response():
                return jsonify({"error": "Mailbox not found"}), 404
            return render_template("http_mail.html",
                                   path=app.config["path"],
                                   hostname=app.config.get("hostname", ""),
                                   max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                                   error="Mailbox not found"), 404

        read_key = request.args.get("key", "")
        query = _sanitize(request.args.get("q", "").strip(), 200)
        sender = _sanitize(request.args.get("sender", "").strip(), 64)

        limit = None
        limit_raw = request.args.get("limit", "").strip()
        if limit_raw:
            try:
                # Keep limits bounded to avoid abuse and huge payloads.
                limit = max(1, min(int(limit_raw), 200))
            except ValueError:
                if _wants_json_response():
                    return jsonify({"error": "Invalid limit value"}), 400
                return render_template(
                    "http_mail.html",
                    path=app.config["path"],
                    hostname=app.config.get("hostname", ""),
                    max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                    error="Invalid limit value",
                    inbox_address=address,
                    inbox_read_key=read_key,
                    inbox_query=query,
                    inbox_sender=sender,
                    inbox_limit=limit_raw,
                ), 400

        messages = mailbox.get_messages(read_key, query=query, sender=sender, limit=limit)

        if messages is None:
            if _wants_json_response():
                return jsonify({"error": "Invalid read key"}), 403
            return render_template("http_mail.html",
                                   path=app.config["path"],
                                   hostname=app.config.get("hostname", ""),
                                   max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                                   error="Invalid read key — access denied"), 403

        if _wants_json_response():
            return jsonify({
                "address": address,
                "messages": messages,
                "filters": {
                    "q": query,
                    "sender": sender,
                    "limit": limit,
                },
            })

        return render_template("http_mail.html",
                               path=app.config["path"],
                               hostname=app.config.get("hostname", ""),
                               max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                               inbox_address=address,
                               inbox_read_key=read_key,
                               inbox_query=query,
                               inbox_sender=sender,
                               inbox_limit=limit if limit is not None else "",
                               messages=messages)

    # ------------------------------------------------------------------
    # Delete a single message (requires read_key in POST body)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/<string:address>/delete/<string:msg_id>',
               methods=["POST"])
    def http_mail_delete_message(url_addition, address, msg_id):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            return jsonify({"error": "Mailbox not found"}), 404

        if request.is_json:
            read_key = (request.get_json() or {}).get("read_key", "")
        else:
            read_key = request.form.get("read_key", "")

        deleted = mailbox.delete_message(read_key, msg_id)

        if not deleted:
            return jsonify({"error": "Invalid read key or message not found"}), 403

        if request.is_json:
            return jsonify({"success": True})

        return redirect(url_for("http_mail_inbox",
                                url_addition=url_addition,
                                address=address,
                                key=read_key))

    # ------------------------------------------------------------------
    # Destroy entire mailbox (requires read_key in POST body)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/<string:address>/destroy', methods=["POST"])
    def http_mail_destroy(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        if request.is_json:
            read_key = (request.get_json() or {}).get("read_key", "")
        else:
            read_key = request.form.get("read_key", "")

        deleted = http_mail_storage.delete_mailbox(address, read_key)

        if not deleted:
            return jsonify({"error": "Invalid read key or mailbox not found"}), 403

        if request.is_json:
            return jsonify({"success": True})

        return render_template("http_mail.html",
                               path=app.config["path"],
                               hostname=app.config.get("hostname", ""),
                               max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                               success="Mailbox destroyed.")
