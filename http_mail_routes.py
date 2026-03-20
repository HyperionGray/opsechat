"""
HTTP Mail Routes for opsechat

Email-over-HTTP: no SMTP, no IMAP — messages are posted to in-memory mailboxes
and read back using a private read_key (default deny).

Routes registered under /<path>/mail/:
  GET  /<path>/mail                        - Main UI (create mailbox form)
  POST /<path>/mail/new                    - Create a new mailbox
  POST /<path>/mail/send                   - Send via address in body (no JS fallback)
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

    def _wants_json() -> bool:
        return request.is_json or request.headers.get("Accept", "").startswith("application/json")

    def _render_send_error(address: str, message: str, status: int):
        if _wants_json():
            return jsonify({"error": message}), status
        return render_template("http_mail.html",
                               path=app.config["path"],
                               hostname=app.config.get("hostname", ""),
                               max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                               error=message,
                               compose_address=address), status

    def _extract_send_fields():
        if request.is_json:
            data = request.get_json() or {}
            return (
                data.get("subject", "").strip(),
                data.get("body", "").strip(),
                data.get("sender", "anonymous").strip(),
            )
        return (
            request.form.get("subject", "").strip(),
            request.form.get("body", "").strip(),
            request.form.get("sender", "anonymous").strip(),
        )

    def _send_message(url_addition: str, address: str):
        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            return _render_send_error(address, "Mailbox not found", 404)

        subject, body, sender = _extract_send_fields()
        subject = _sanitize(subject, 200) or "(no subject)"
        body = _sanitize(body, MAX_MAIL_MESSAGE_LENGTH)
        sender = _sanitize(sender, 64) or "anonymous"

        if not body:
            return _render_send_error(address, "Message body is required", 400)

        try:
            msg_id = mailbox.add_message(subject=subject, body=body, sender_handle=sender)
        except RuntimeError:
            return _render_send_error(address, "Mailbox not found", 404)

        if _wants_json():
            return jsonify({"success": True, "msg_id": msg_id})

        return render_template("http_mail.html",
                               path=app.config["path"],
                               hostname=app.config.get("hostname", ""),
                               max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                               success="Message sent.",
                               compose_address=address)

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
    # Send a message to a mailbox (no authentication required)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/send', methods=["POST"])
    def http_mail_send_fallback(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        if request.is_json:
            address = ((request.get_json() or {}).get("address") or "").strip()
        else:
            address = (request.form.get("_address_override", "") or request.form.get("address", "")).strip()

        if not address:
            return _render_send_error("", "Recipient mailbox address is required", 400)

        return _send_message(url_addition, address)

    @app.route('/<string:url_addition>/mail/<string:address>/send', methods=["POST"])
    def http_mail_send(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        return _send_message(url_addition, address)

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
            return render_template("http_mail.html",
                                   path=app.config["path"],
                                   hostname=app.config.get("hostname", ""),
                                   max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                                   error="Mailbox not found"), 404

        read_key = request.args.get("key", "")
        messages = mailbox.get_messages(read_key)

        if messages is None:
            if request.headers.get("Accept", "").startswith("application/json"):
                return jsonify({"error": "Invalid read key"}), 403
            return render_template("http_mail.html",
                                   path=app.config["path"],
                                   hostname=app.config.get("hostname", ""),
                                   max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                                   error="Invalid read key — access denied"), 403

        if request.headers.get("Accept", "").startswith("application/json"):
            return jsonify({"address": address, "messages": messages})

        return render_template("http_mail.html",
                               path=app.config["path"],
                               hostname=app.config.get("hostname", ""),
                               max_message_length=MAX_MAIL_MESSAGE_LENGTH,
                               inbox_address=address,
                               inbox_read_key=read_key,
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
