"""
HTTP Mail Routes for opsechat

Email-over-HTTP: no SMTP, no IMAP — messages are posted to in-memory mailboxes
and read back using a private read_key (default deny).

Routes registered under /<path>/mail/:
  GET  /<path>/mail                        - Main UI (create mailbox form)
  POST /<path>/mail/new                    - Create a new mailbox
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

    def _render_http_mail(**kwargs):
        """Render HTTP mail template with shared defaults."""
        context = {
            "path": app.config["path"],
            "hostname": app.config.get("hostname", ""),
            "max_message_length": MAX_MAIL_MESSAGE_LENGTH,
        }
        context.update(kwargs)
        return render_template("http_mail.html", **context)

    # ------------------------------------------------------------------
    # Main UI — create or access mailbox
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail', methods=["GET"])
    def http_mail_index(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        return _render_http_mail()

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
    # Send a message to a mailbox (no authentication required)
    # ------------------------------------------------------------------

    def _send_to_mailbox(address):
        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            if request.is_json:
                return jsonify({"error": "Mailbox not found"}), 404
            return _render_http_mail(
                error="Mailbox not found",
                compose_address=address
            ), 404

        # Accept JSON or form data
        if request.is_json:
            data = request.get_json() or {}
            subject = data.get("subject", "").strip()
            body = data.get("body", "").strip()
            sender = data.get("sender", "anonymous").strip()
        else:
            subject = request.form.get("subject", "").strip()
            body = request.form.get("body", "").strip()
            sender = request.form.get("sender", "anonymous").strip()

        if not body:
            if request.is_json:
                return jsonify({"error": "Message body is required"}), 400
            return _render_http_mail(
                error="Message body is required",
                compose_address=address
            ), 400

        subject = _sanitize(subject, 200) or "(no subject)"
        body = _sanitize(body, MAX_MAIL_MESSAGE_LENGTH)
        sender = _sanitize(sender, 64) or "anonymous"

        try:
            msg_id = mailbox.add_message(subject=subject, body=body, sender_handle=sender)
        except RuntimeError:
            # Mailbox was concurrently destroyed after lookup.
            if request.is_json:
                return jsonify({"error": "Mailbox not found"}), 404
            return _render_http_mail(
                error="Mailbox not found",
                compose_address=address
            ), 404

        if request.is_json:
            return jsonify({"success": True, "msg_id": msg_id})

        return _render_http_mail(
            success="Message sent.",
            compose_address=address
        )

    @app.route('/<string:url_addition>/mail/send', methods=["POST"])
    def http_mail_send_form(url_addition):
        """No-JavaScript fallback route where the address comes from form input."""
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        address = request.form.get("_address_override", "").strip()
        if not address:
            return _render_http_mail(
                error="Recipient mailbox address is required"
            ), 400

        return _send_to_mailbox(address)

    @app.route('/<string:url_addition>/mail/<string:address>/send', methods=["POST"])
    def http_mail_send(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        return _send_to_mailbox(address)

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
            if request.headers.get("Accept", "").startswith("application/json"):
                return jsonify({"error": "Mailbox not found"}), 404
            return _render_http_mail(error="Mailbox not found"), 404

        read_key = request.args.get("key", "")
        messages = mailbox.get_messages(read_key)

        if messages is None:
            if request.headers.get("Accept", "").startswith("application/json"):
                return jsonify({"error": "Invalid read key"}), 403
            return _render_http_mail(error="Invalid read key — access denied"), 403

        if request.headers.get("Accept", "").startswith("application/json"):
            return jsonify({"address": address, "messages": messages})

        return _render_http_mail(
            inbox_address=address,
            inbox_read_key=read_key,
            messages=messages
        )

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
    # Rotate mailbox read key (requires current read_key)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/<string:address>/rotate-key', methods=["POST"])
    def http_mail_rotate_key(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        if request.is_json:
            read_key = (request.get_json() or {}).get("read_key", "")
        else:
            read_key = request.form.get("read_key", "")

        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            if request.is_json:
                return jsonify({"error": "Mailbox not found"}), 404
            return _render_http_mail(error="Mailbox not found"), 404

        new_read_key = http_mail_storage.rotate_read_key(address, read_key)
        if new_read_key is None:
            if request.is_json:
                return jsonify({"error": "Invalid read key"}), 403
            return _render_http_mail(
                error="Invalid read key — cannot rotate key",
                inbox_address=address,
                inbox_read_key=read_key
            ), 403

        if request.is_json:
            return jsonify({"success": True, "new_read_key": new_read_key})

        messages = mailbox.get_messages(new_read_key) or []
        return _render_http_mail(
            success="Read key rotated. Save your new key now.",
            inbox_address=address,
            inbox_read_key=new_read_key,
            new_read_key=new_read_key,
            messages=messages
        )

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

        return _render_http_mail(success="Mailbox destroyed.")
