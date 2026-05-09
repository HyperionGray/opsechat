"""
HTTP Mail Routes for opsechat

Email-over-HTTP: no SMTP, no IMAP — messages are posted to inboxes keyed by a
shareable username and decrypted in the browser with a private inbox key.

Routes registered under /<path>/mail/:
  GET  /<path>/mail                        - Main UI (create mailbox form)
  POST /<path>/mail/new                    - Create a new mailbox
  POST /<path>/mail/<address>/send        - Send a message to a mailbox
  GET  /<path>/mail/<address>/inbox       - Read inbox ciphertext
  POST /<path>/mail/<address>/delete/<id> - Delete a message
  POST /<path>/mail/<address>/destroy     - Delete entire mailbox
"""

from flask import render_template, request, jsonify, redirect, url_for
from http_mail_system import (
    http_mail_storage,
    MAX_MAIL_MESSAGE_LENGTH,
    generate_mailbox_alias,
)

CIPHERTEXT_STORAGE_MULTIPLIER = 10


def register_http_mail_routes(app):
    """Register HTTP mail routes with the Flask app."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_mailbox(address: str):
        return (
            http_mail_storage.get_mailbox(address)
            or http_mail_storage.get_mailbox_by_alias(address)
        )

    def _render_http_mail(**kwargs):
        defaults = {
            "path": app.config["path"],
            "hostname": app.config.get("hostname", ""),
            "max_message_length": MAX_MAIL_MESSAGE_LENGTH,
        }
        defaults.update(kwargs)
        return render_template("http_mail.html", **defaults)

    # ------------------------------------------------------------------
    # Main UI — create or access mailbox
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail', methods=["GET"])
    def http_mail_index(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        return _render_http_mail()

    # ------------------------------------------------------------------
    # Create a new mailbox
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/mail/new', methods=["POST"])
    def http_mail_create(url_addition):
        if url_addition != app.config["path"]:
            return ('', 404)
        while True:
            alias = generate_mailbox_alias()
            if _resolve_mailbox(alias) is not None:
                continue
            try:
                mailbox = http_mail_storage.create_mailbox(alias=alias)
                break
            except ValueError as error:
                if str(error) != "Mailbox alias already exists":
                    raise
                continue
        response_payload = {
            "success": True,
            "address": alias,
            "username": alias,
            "read_key": mailbox.read_key,
            "send_url": f"/{url_addition}/mail/{alias}/send",
            "inbox_url": f"/{url_addition}/mail/{alias}/inbox",
        }

        response_mode = request.form.get("response_mode", "").strip().lower()
        accepts_html = "text/html" in request.headers.get("Accept", "")
        if response_mode != "html" and not accepts_html:
            return jsonify(response_payload)

        return _render_http_mail(
            success=(
                "Inbox created. Save the username and inbox key before "
                "leaving this page."
            ),
            created_mailbox=response_payload,
        )

    @app.route('/<string:url_addition>/mail/send', methods=["POST"])
    def http_mail_send_generic(url_addition):
        """Form-friendly send endpoint that resolves the mailbox address."""
        if url_addition != app.config["path"]:
            return ('', 404)

        address = (
            request.form.get("_address_override", "").strip()
            or request.form.get("address", "").strip()
        )
        if not address:
            return _render_http_mail(
                error="Recipient mailbox address is required",
                compose_address="",
            ), 400

        return http_mail_send(url_addition, address)

    # ------------------------------------------------------------------
    # Send a message to a mailbox (no authentication required)
    # ------------------------------------------------------------------

    @app.route(
        '/<string:url_addition>/mail/<string:address>/send',
        methods=["POST"],
    )
    def http_mail_send(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)

        mailbox = _resolve_mailbox(address)
        if mailbox is None:
            if request.is_json:
                return jsonify({"error": "Mailbox not found"}), 404
            return _render_http_mail(
                error="Mailbox not found",
                compose_address=address,
                initial_section="compose",
            ), 404

        # Accept JSON or form data, but only store browser-encrypted payloads.
        if request.is_json:
            data = request.get_json() or {}
            ciphertext = (data.get("ciphertext") or "").strip()
        else:
            ciphertext = request.form.get("ciphertext", "").strip()

        if not ciphertext:
            if request.is_json:
                return jsonify(
                    {"error": "Browser-side encrypted ciphertext is required"}
                ), 400
            return _render_http_mail(
                error="Browser-side encrypted ciphertext is required",
                compose_address=address,
                initial_section="compose",
            ), 400

        max_ciphertext_length = (
            MAX_MAIL_MESSAGE_LENGTH * CIPHERTEXT_STORAGE_MULTIPLIER
        )
        if len(ciphertext) > max_ciphertext_length:
            error_message = (
                "Encrypted payload is too large to store safely. "
                "Shorten the message and try again."
            )
            if request.is_json:
                return jsonify({"error": error_message}), 400
            return _render_http_mail(
                error=error_message,
                compose_address=address,
                initial_section="compose",
            ), 400

        msg_id = mailbox.add_encrypted_message(
            ciphertext
        )

        if request.is_json:
            return jsonify({"success": True, "msg_id": msg_id})

        return _render_http_mail(
            success="Message sent.",
            compose_address=address,
        )

    @app.route('/<string:url_addition>/mail/open', methods=["GET"])
    def http_mail_open(url_addition):
        """Helper that redirects to the username-scoped inbox route."""
        if url_addition != app.config["path"]:
            return ('', 404)

        address = (
            request.args.get("address", "").strip()
            or request.args.get("_read_address", "").strip()
        )

        if not address:
            return _render_http_mail(
                error="Inbox username is required",
                inbox_address=address,
                initial_section="read",
            ), 400

        inbox_args = {
            "url_addition": url_addition,
            "address": address,
        }
        read_key = (
            request.args.get("key", "").strip()
            or request.args.get("_read_key", "").strip()
        )
        if read_key:
            inbox_args["key"] = read_key

        return redirect(url_for("http_mail_inbox", **inbox_args))

    # ------------------------------------------------------------------
    # Read inbox ciphertext (decryption stays in the browser)
    # ------------------------------------------------------------------

    @app.route(
        '/<string:url_addition>/mail/<string:address>/inbox',
        methods=["GET"],
    )
    def http_mail_inbox(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)

        mailbox = _resolve_mailbox(address)
        if mailbox is None:
            if request.headers.get("Accept", "").startswith(
                "application/json"
            ):
                return jsonify({"error": "Mailbox not found"}), 404
            return _render_http_mail(error="Mailbox not found"), 404

        messages = mailbox.get_messages()

        if request.headers.get("Accept", "").startswith("application/json"):
            return jsonify({"address": address, "messages": messages})

        return _render_http_mail(
            inbox_address=address,
            inbox_read_key=request.args.get("key", "").strip(),
            messages=messages,
            initial_section="read",
        )

    # ------------------------------------------------------------------
    # Delete a single message (requires read_key in POST body)
    # ------------------------------------------------------------------

    @app.route(
        '/<string:url_addition>/mail/<string:address>/delete/<string:msg_id>',
        methods=["POST"],
    )
    def http_mail_delete_message(url_addition, address, msg_id):
        if url_addition != app.config["path"]:
            return ('', 404)
        mailbox = _resolve_mailbox(address)
        if mailbox is None:
            if request.is_json:
                return jsonify({"error": "Mailbox not found"}), 404
            # read_key not available yet when mailbox is not found
            return _render_http_mail(
                error="Mailbox not found",
                inbox_address=address,
                initial_section="read",
            ), 404

        if request.is_json:
            read_key = (request.get_json() or {}).get("read_key", "")
        else:
            read_key = request.form.get("read_key", "")

        deleted = mailbox.delete_message(read_key, msg_id)

        if not deleted:
            if request.is_json:
                return jsonify(
                    {"error": "Invalid read key or message not found"}
                ), 403
            return _render_http_mail(
                error="Invalid read key or message not found",
                inbox_address=address,
                inbox_read_key=read_key,
                initial_section="read",
            ), 403

        if request.is_json:
            return jsonify({"success": True})

        return redirect(
            url_for(
                "http_mail_inbox",
                url_addition=url_addition,
                address=address,
                key=read_key,
            )
        )

    # ------------------------------------------------------------------
    # Destroy entire mailbox (requires read_key in POST body)
    # ------------------------------------------------------------------

    @app.route(
        '/<string:url_addition>/mail/<string:address>/destroy',
        methods=["POST"],
    )
    def http_mail_destroy(url_addition, address):
        if url_addition != app.config["path"]:
            return ('', 404)

        if request.is_json:
            read_key = (request.get_json() or {}).get("read_key", "")
        else:
            read_key = request.form.get("read_key", "")

        mailbox = _resolve_mailbox(address)
        if mailbox is None:
            if request.is_json:
                return jsonify({"error": "Mailbox not found"}), 404
            return _render_http_mail(
                error="Mailbox not found",
                inbox_address=address,
                inbox_read_key=read_key,
                initial_section="read",
            ), 404

        deleted = http_mail_storage.delete_mailbox(mailbox.address, read_key)

        if not deleted:
            if request.is_json:
                return jsonify(
                    {"error": "Invalid read key or mailbox not found"}
                ), 403
            return _render_http_mail(
                error="Invalid read key or mailbox not found",
                inbox_address=address,
                inbox_read_key=read_key,
                initial_section="read",
            ), 403

        if request.is_json:
            return jsonify({"success": True})

        return _render_http_mail(success="Mailbox destroyed.")
