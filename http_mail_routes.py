"""
HTTP Mail Routes for opsechat

Email-over-HTTP: no SMTP, no IMAP — messages are posted to in-memory mailboxes
and read back using a private read_key (default deny).

Routes registered under /<path>/mail/:
  GET  /<path>/mail                         - Main UI (create/access mailbox)
  POST /<path>/mail/new                     - Create a new mailbox
  POST /<path>/mail/send                    - Form fallback send route
  POST /<path>/mail/<address>/send          - Send a message to a mailbox
  GET  /<path>/mail/my/list.json            - List mailboxes tracked in this session
  GET  /<path>/mail/<address>/inbox         - Read inbox (requires ?key=<read_key>)
  POST /<path>/mail/<address>/delete/<id>   - Delete a message (requires read_key)
  POST /<path>/mail/<address>/destroy       - Delete entire mailbox (requires read_key)
"""

import re
from flask import render_template, request, session, jsonify, redirect, url_for
from http_mail_system import http_mail_storage, MAX_MAIL_MESSAGE_LENGTH
from utils import id_generator, get_random_color


SESSION_MAILBOXES_KEY = "http_mail_mailboxes"


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
        accept = request.headers.get("Accept", "")
        return request.is_json or ("application/json" in accept)

    def _session_mailboxes_raw():
        raw = session.get(SESSION_MAILBOXES_KEY, [])
        if not isinstance(raw, list):
            return []

        cleaned = []
        seen = set()
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            address = str(entry.get("address", "")).strip()
            read_key = str(entry.get("read_key", "")).strip()
            if not address or not read_key or address in seen:
                continue
            seen.add(address)
            cleaned.append({"address": address, "read_key": read_key})
        return cleaned

    def _save_session_mailboxes(mailboxes):
        session[SESSION_MAILBOXES_KEY] = mailboxes
        session.modified = True

    def _remember_mailbox(address: str, read_key: str):
        tracked = _session_mailboxes_raw()
        tracked = [m for m in tracked if m["address"] != address]
        tracked.append({"address": address, "read_key": read_key})
        _save_session_mailboxes(tracked)

    def _forget_mailbox(address: str):
        tracked = _session_mailboxes_raw()
        filtered = [m for m in tracked if m["address"] != address]
        if len(filtered) != len(tracked):
            _save_session_mailboxes(filtered)

    def _tracked_mailbox_views():
        tracked = _session_mailboxes_raw()
        cleaned = []
        views = []

        for entry in tracked:
            address = entry["address"]
            read_key = entry["read_key"]
            mailbox = http_mail_storage.get_mailbox(address)
            if mailbox is None:
                continue

            messages = mailbox.get_messages(read_key)
            if messages is None:
                continue

            views.append({
                "address": address,
                "read_key": read_key,
                "message_count": len(messages),
                "last_message_timestamp": messages[-1]["timestamp"] if messages else None,
                "inbox_url": f"/{app.config['path']}/mail/{address}/inbox?key={read_key}",
            })
            cleaned.append(entry)

        if len(cleaned) != len(tracked):
            _save_session_mailboxes(cleaned)

        return views

    def _render_mail_page(**kwargs):
        context = {
            "path": app.config["path"],
            "hostname": app.config.get("hostname", ""),
            "max_message_length": MAX_MAIL_MESSAGE_LENGTH,
            "tracked_mailboxes": _tracked_mailbox_views(),
        }
        context.update(kwargs)
        return render_template("http_mail.html", **context)

    def _send_message_to_mailbox(address: str):
        mailbox = http_mail_storage.get_mailbox(address)
        if mailbox is None:
            if request.is_json:
                return jsonify({"error": "Mailbox not found"}), 404
            return _render_mail_page(error="Mailbox not found",
                                     compose_address=address), 404

        # Accept JSON or form data
        if request.is_json:
            data = request.get_json(silent=True) or {}
            subject = str(data.get("subject", "")).strip()
            body = str(data.get("body", "")).strip()
            sender = str(data.get("sender", "anonymous")).strip()
        else:
            subject = request.form.get("subject", "").strip()
            body = request.form.get("body", "").strip()
            sender = request.form.get("sender", "anonymous").strip()

        if not body:
            if request.is_json:
                return jsonify({"error": "Message body is required"}), 400
            return _render_mail_page(error="Message body is required",
                                     compose_address=address), 400

        subject = _sanitize(subject, 200) or "(no subject)"
        body = _sanitize(body, MAX_MAIL_MESSAGE_LENGTH)
        sender = _sanitize(sender, 64) or "anonymous"
        msg_id = mailbox.add_message(subject=subject, body=body, sender_handle=sender)

        if msg_id is None:
            if request.is_json:
                return jsonify({"error": "Mailbox is no longer available"}), 410
            return _render_mail_page(error="Mailbox is no longer available",
                                     compose_address=address), 410

        if request.is_json:
            return jsonify({"success": True, "msg_id": msg_id})

        return _render_mail_page(success="Message sent.", compose_address=address)

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
        _remember_mailbox(mailbox.address, mailbox.read_key)

        # JSON response — UI can cache address/read_key client-side if desired.
        return jsonify({
            "success": True,
            "address": mailbox.address,
            "read_key": mailbox.read_key,
            "send_url": f"/{url_addition}/mail/{mailbox.address}/send",
            "inbox_url": f"/{url_addition}/mail/{mailbox.address}/inbox",
        })

    # ------------------------------------------------------------------
    # Form fallback for message send (non-JS compose action)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/send', methods=["POST"])
    def http_mail_send_form(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        address = request.form.get("_address_override", "").strip()
        if not address:
            return _render_mail_page(error="Recipient mailbox address is required",
                                     compose_address=""), 400
        return _send_message_to_mailbox(address)

    # ------------------------------------------------------------------
    # Send a message to a mailbox (API + direct form path)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/<string:address>/send', methods=["POST"])
    def http_mail_send(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()
        return _send_message_to_mailbox(address)

    # ------------------------------------------------------------------
    # Session mailbox list + stats
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/my/list.json', methods=["GET"])
    def http_mail_my_list(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        _ensure_session()

        mailboxes = _tracked_mailbox_views()
        return jsonify({
            "mailboxes": mailboxes,
            "stats": {
                "tracked_mailboxes": len(mailboxes),
                "total_messages": sum(m["message_count"] for m in mailboxes),
            },
        })

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
            return _render_mail_page(error="Mailbox not found"), 404

        read_key = request.args.get("key", "")
        messages = mailbox.get_messages(read_key)
        if messages is None:
            if _wants_json_response():
                return jsonify({"error": "Invalid read key"}), 403
            return _render_mail_page(error="Invalid read key — access denied"), 403

        _remember_mailbox(address, read_key)

        if _wants_json_response():
            return jsonify({
                "address": address,
                "messages": messages,
                "message_count": len(messages),
            })

        return _render_mail_page(inbox_address=address,
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
            read_key = (request.get_json(silent=True) or {}).get("read_key", "")
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
            read_key = (request.get_json(silent=True) or {}).get("read_key", "")
        else:
            read_key = request.form.get("read_key", "")

        deleted = http_mail_storage.delete_mailbox(address, read_key)
        if not deleted:
            return jsonify({"error": "Invalid read key or mailbox not found"}), 403

        _forget_mailbox(address)

        if request.is_json:
            return jsonify({"success": True})

        return _render_mail_page(success="Mailbox destroyed.")
