"""
HTTP Mail Routes for opsechat

Email-over-HTTP: no SMTP, no IMAP — messages are posted to in-memory mailboxes
and read back using a private read_key (default deny).

Routes registered under /<path>/mail/:
  GET  /<path>/mail                        - Main UI (create mailbox form)
  POST /<path>/mail/new                    - Create a new mailbox
  POST /<path>/mail/send                   - Non-JS fallback send endpoint
  POST /<path>/mail/<address>/send         - Send a message to a mailbox (no auth)
  GET  /<path>/mail/<address>/inbox        - Read inbox (requires ?key=<read_key>)
                                            Supports JSON query params:
                                              limit, offset, include_body, order
  GET  /<path>/mail/<address>/status       - Mailbox metadata (count/timestamps)
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

    def _mail_page(**kwargs):
        """Render HTTP mail UI with shared template arguments."""
        base_kwargs = {
            "path": app.config["path"],
            "hostname": app.config.get("hostname", ""),
            "max_message_length": MAX_MAIL_MESSAGE_LENGTH,
        }
        base_kwargs.update(kwargs)
        return render_template("http_mail.html", **base_kwargs)

    def _wants_json_response() -> bool:
        accept = request.headers.get("Accept", "").lower()
        return request.is_json or "application/json" in accept

    def _parse_bool(value, default: bool = True) -> bool:
        if value is None:
            return default
        value = str(value).strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        return default

    def _parse_int_arg(name: str, default: int, minimum: int, maximum: int = None) -> int:
        raw = request.args.get(name)
        if raw is None:
            return default
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be an integer")
        if parsed < minimum:
            raise ValueError(f"{name} must be >= {minimum}")
        if maximum is not None and parsed > maximum:
            raise ValueError(f"{name} must be <= {maximum}")
        return parsed

    def _send_to_mailbox(address: str):
        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            if _wants_json_response():
                return jsonify({"error": "Mailbox not found"}), 404
            return _mail_page(error="Mailbox not found", compose_address=address), 404

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
            if _wants_json_response():
                return jsonify({"error": "Message body is required"}), 400
            return _mail_page(
                error="Message body is required",
                compose_address=address
            ), 400

        subject = _sanitize(subject, 200) or "(no subject)"
        body = _sanitize(body, MAX_MAIL_MESSAGE_LENGTH)
        sender = _sanitize(sender, 64) or "anonymous"

        try:
            msg_id = mailbox.add_message(subject=subject, body=body, sender_handle=sender)
        except RuntimeError:
            return jsonify({"error": "Mailbox no longer accepts messages"}), 410

        if _wants_json_response():
            return jsonify({"success": True, "msg_id": msg_id})

        return _mail_page(success="Message sent.", compose_address=address)

    # ------------------------------------------------------------------
    # Main UI — create or access mailbox
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail', methods=["GET"])
    def http_mail_index(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        return _mail_page()

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

    @app.route('/<string:url_addition>/mail/<string:address>/send', methods=["POST"])
    def http_mail_send(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        return _send_to_mailbox(address)

    @app.route('/<string:url_addition>/mail/send', methods=["POST"])
    def http_mail_send_fallback(url_addition):
        """Non-JS fallback endpoint for compose form."""
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        address = request.form.get("_address_override", "").strip()
        if not address:
            return _mail_page(
                error="Recipient mailbox address is required",
                compose_address=""
            ), 400
        address = _sanitize(address, 64)
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
            if _wants_json_response():
                return jsonify({"error": "Mailbox not found"}), 404
            return _mail_page(error="Mailbox not found"), 404

        read_key = request.args.get("key", "")
        if _wants_json_response():
            try:
                limit = _parse_int_arg("limit", 50, minimum=1, maximum=200)
                offset = _parse_int_arg("offset", 0, minimum=0)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

            include_body = _parse_bool(request.args.get("include_body"), default=True)
            order = request.args.get("order", "oldest").strip().lower()
            if order not in {"oldest", "newest"}:
                return jsonify({"error": "order must be 'oldest' or 'newest'"}), 400
            newest_first = order == "newest"

            messages = mailbox.get_messages(
                read_key,
                limit=limit,
                offset=offset,
                include_body=include_body,
                newest_first=newest_first,
            )
            if messages is None:
                return jsonify({"error": "Invalid read key"}), 403

            total_messages = mailbox.message_count()
            return jsonify({
                "address": address,
                "messages": messages,
                "total_messages": total_messages,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(messages)) < total_messages,
                "include_body": include_body,
                "order": order,
            })

        messages = mailbox.get_messages(read_key)
        if messages is None:
            return _mail_page(error="Invalid read key — access denied"), 403

        return _mail_page(
            inbox_address=address,
            inbox_read_key=read_key,
            messages=messages
        )

    @app.route('/<string:url_addition>/mail/<string:address>/status', methods=["GET"])
    def http_mail_status(url_addition, address):
        """Get mailbox metadata without returning message bodies."""
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            return jsonify({"error": "Mailbox not found"}), 404

        read_key = request.args.get("key", "")
        status = mailbox.get_status(read_key)
        if status is None:
            return jsonify({"error": "Invalid read key"}), 403
        return jsonify({"address": address, **status})

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

        return _mail_page(success="Mailbox destroyed.")
