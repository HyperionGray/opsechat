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

import datetime
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

    def _render_mail_page(status_code: int = 200, **context):
        rendered = render_template(
            "http_mail.html",
            path=app.config["path"],
            hostname=app.config.get("hostname", ""),
            max_message_length=MAX_MAIL_MESSAGE_LENGTH,
            **context,
        )
        if status_code == 200:
            return rendered
        return rendered, status_code

    def _parse_int_arg(name: str, minimum: int, maximum: int = None):
        raw = request.args.get(name)
        if raw in (None, ""):
            return None, None
        try:
            value = int(raw)
        except ValueError:
            return None, f"{name} must be an integer"
        if value < minimum:
            return None, f"{name} must be >= {minimum}"
        if maximum is not None and value > maximum:
            return None, f"{name} must be <= {maximum}"
        return value, None

    def _parse_since_arg():
        raw = request.args.get("since", "").strip()
        if not raw:
            return None, None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.datetime.fromisoformat(normalized)
        except ValueError:
            return None, "since must be an ISO-8601 datetime"
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return parsed, None

    # ------------------------------------------------------------------
    # Main UI — create or access mailbox
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail', methods=["GET"])
    def http_mail_index(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        return _render_mail_page()

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

        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            return jsonify({"error": "Mailbox not found"}), 404

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
            return _render_mail_page(
                400,
                error="Message body is required",
                compose_address=address,
            )

        subject = _sanitize(subject, 200) or "(no subject)"
        body = _sanitize(body, MAX_MAIL_MESSAGE_LENGTH)
        sender = _sanitize(sender, 64) or "anonymous"

        msg_id = mailbox.add_message(subject=subject, body=body, sender_handle=sender)

        if request.is_json:
            return jsonify({"success": True, "msg_id": msg_id})

        return _render_mail_page(
            success="Message sent.",
            compose_address=address,
        )

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
            if _wants_json():
                return jsonify({"error": "Mailbox not found"}), 404
            return _render_mail_page(404, error="Mailbox not found")

        read_key = request.args.get("key", "")
        sender_filter = request.args.get("sender", "").strip()
        subject_filter = request.args.get("subject", "").strip()
        since_filter, since_error = _parse_since_arg()
        if since_error:
            if _wants_json():
                return jsonify({"error": since_error}), 400
            return _render_mail_page(400, error=since_error)

        limit_filter, limit_error = _parse_int_arg("limit", minimum=1, maximum=200)
        if limit_error:
            if _wants_json():
                return jsonify({"error": limit_error}), 400
            return _render_mail_page(400, error=limit_error)

        offset_filter, offset_error = _parse_int_arg("offset", minimum=0)
        if offset_error:
            if _wants_json():
                return jsonify({"error": offset_error}), 400
            return _render_mail_page(400, error=offset_error)

        order_filter = request.args.get("order", "desc").strip().lower() or "desc"
        if order_filter not in ("asc", "desc"):
            msg = "order must be 'asc' or 'desc'"
            if _wants_json():
                return jsonify({"error": msg}), 400
            return _render_mail_page(400, error=msg)

        query_result = mailbox.query_messages(
            read_key=read_key,
            sender_contains=sender_filter,
            subject_contains=subject_filter,
            since=since_filter,
            limit=limit_filter,
            offset=offset_filter or 0,
            order=order_filter,
        )

        if query_result is None:
            if _wants_json():
                return jsonify({"error": "Invalid read key"}), 403
            return _render_mail_page(403, error="Invalid read key — access denied")

        applied_filters = {
            "sender": sender_filter,
            "subject": subject_filter,
            "since": request.args.get("since", "").strip(),
            "limit": limit_filter if limit_filter is not None else "",
            "offset": offset_filter if offset_filter is not None else 0,
            "order": order_filter,
        }

        if _wants_json():
            return jsonify({
                "address": address,
                "messages": query_result["messages"],
                "total_messages": query_result["total"],
                "returned_messages": query_result["returned"],
                "filters": {
                    "sender": sender_filter,
                    "subject": subject_filter,
                    "since": request.args.get("since", "").strip(),
                    "limit": limit_filter,
                    "offset": offset_filter or 0,
                    "order": order_filter,
                },
            })

        return _render_mail_page(
            inbox_address=address,
            inbox_read_key=read_key,
            messages=query_result["messages"],
            total_messages=query_result["total"],
            applied_filters=applied_filters,
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

        redirect_args = {
            "url_addition": url_addition,
            "address": address,
            "key": read_key,
        }
        for key in ("sender", "subject", "since", "limit", "offset", "order"):
            value = request.form.get(key, "").strip()
            if value:
                redirect_args[key] = value

        return redirect(url_for("http_mail_inbox",
                                **redirect_args))

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

        return _render_mail_page(success="Mailbox destroyed.")
