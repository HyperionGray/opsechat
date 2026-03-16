"""
Email system routes for opsechat

This module contains Flask routes for email functionality including:
- Email inbox management
- Email composition and sending
- Burner email system
- Email security tools (spoofing detection, phishing simulation)
- Email configuration management
"""

from flask import render_template, request, session, jsonify, redirect, url_for
from email_system import email_storage, burner_manager, EmailComposer, EmailValidator
from email_security_tools import spoofing_tester, phishing_simulator
from email_transport import transport_manager
from domain_manager import domain_rotation_manager, PorkbunAPIClient


def register_email_routes(app, id_generator, get_random_color):
    """Register all email-related routes with the Flask app"""

    def _ensure_session_user():
        """Ensure the session has user identity and color."""
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()

    def _set_config_message(message_type, text):
        """Store one-shot message shown on config page."""
        session["_email_config_message"] = {
            "type": message_type,
            "text": text
        }

    def _to_int(value, default):
        """Best-effort integer parser for form values."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @app.route('/<string:url_addition>/email', methods=["GET"])
    def email_inbox(url_addition):
        """Main email inbox page"""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session_user()

        # Initialize inbox for user
        email_storage.create_user_inbox(session["_id"])

        # Get emails
        emails = email_storage.get_emails(session["_id"])

        return render_template("email_inbox.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              emails=emails,
                              script_enabled=False)

    @app.route('/<string:url_addition>/email/yesscript', methods=["GET"])
    def email_inbox_script(url_addition):
        """Email inbox with JavaScript enabled"""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session_user()

        email_storage.create_user_inbox(session["_id"])
        emails = email_storage.get_emails(session["_id"])

        return render_template("email_inbox.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              emails=emails,
                              script_enabled=True)

    @app.route('/<string:url_addition>/email/burner', methods=["GET", "POST"])
    def email_burner(url_addition):
        """Burner email management page (generate/rotate supported)."""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session_user()
        burner_manager.cleanup_expired()

        if request.method == "POST":
            action = request.form.get("action", "").strip().lower()
            if action == "generate":
                burner_manager.generate_burner_email(session["_id"])
            elif action == "rotate":
                old_email = request.form.get("old_email", "").strip()
                burner_manager.rotate_burner(session["_id"], old_email or None)

        active_burners = burner_manager.get_user_burners(session["_id"])
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              active_burners=active_burners,
                              script_enabled=False)

    @app.route('/<string:url_addition>/email/burner/yesscript', methods=["GET"])
    def email_burner_script(url_addition):
        """Burner email management with JavaScript"""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session_user()
        burner_manager.cleanup_expired()
        active_burners = burner_manager.get_user_burners(session["_id"])

        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              active_burners=active_burners,
                              script_enabled=True)

    @app.route('/<string:url_addition>/email/burner/list', methods=["GET"])
    def email_burner_list(url_addition):
        """List active burners as plain list JSON (used by JS auto-refresh)."""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            return jsonify([])

        burner_manager.cleanup_expired()
        burners = burner_manager.get_user_burners(session["_id"])
        return jsonify(burners)

    @app.route('/<string:url_addition>/email/burner/list.json', methods=["GET"])
    def email_burner_list_json(url_addition):
        """JSON API for burner email list + aggregate stats."""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            return jsonify({"error": "No session"}), 401

        burner_manager.cleanup_expired()
        burner_emails = burner_manager.get_user_burners(session["_id"])
        return jsonify({
            "burners": burner_emails,
            "stats": burner_manager.get_user_stats(session["_id"])
        })

    @app.route('/<string:url_addition>/email/burner/expire/<string:email>', methods=["POST"])
    def email_burner_expire(url_addition, email):
        """Expire a specific burner email owned by the current session."""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            return ('Unauthorized', 401)

        burner_user = burner_manager.get_user_for_burner(email)
        if burner_user == session["_id"]:
            burner_manager.expire_burner(email)

        return redirect(url_for('email_burner', url_addition=url_addition))

    @app.route('/<string:url_addition>/email/config', methods=["GET", "POST"])
    def email_config(url_addition):
        """Email configuration page"""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session_user()
        message = session.pop("_email_config_message", None)

        if request.method == "POST":
            action = request.form.get("action", "").strip().lower()

            if action == "configure_smtp":
                smtp_server = request.form.get("smtp_server", "").strip()
                smtp_port = _to_int(request.form.get("smtp_port"), 587)
                smtp_username = request.form.get("smtp_username", "").strip()
                smtp_password = request.form.get("smtp_password", "")
                use_tls = request.form.get("use_tls") == "true"

                if not smtp_server or not smtp_username or not smtp_password:
                    _set_config_message("error", "SMTP server, username, and password are required.")
                else:
                    configured = transport_manager.configure_smtp(
                        smtp_server, smtp_port, smtp_username, smtp_password, use_tls
                    )
                    if configured:
                        _set_config_message("success", "SMTP configured successfully.")
                    else:
                        _set_config_message(
                            "error",
                            "SMTP configuration test failed. Verify credentials/server settings."
                        )

            elif action == "configure_imap":
                imap_server = request.form.get("imap_server", "").strip()
                imap_port = _to_int(request.form.get("imap_port"), 993)
                imap_username = request.form.get("imap_username", "").strip()
                imap_password = request.form.get("imap_password", "")
                use_ssl = request.form.get("use_ssl") == "true"

                if not imap_server or not imap_username or not imap_password:
                    _set_config_message("error", "IMAP server, username, and password are required.")
                else:
                    configured = transport_manager.configure_imap(
                        imap_server, imap_port, imap_username, imap_password, use_ssl
                    )
                    if configured:
                        _set_config_message("success", "IMAP configured successfully.")
                    else:
                        _set_config_message(
                            "error",
                            "IMAP configuration test failed. Verify credentials/server settings."
                        )

            elif action == "configure_domain_api":
                api_key = request.form.get("api_key", "").strip()
                api_secret = request.form.get("api_secret", "").strip()
                monthly_budget = request.form.get("monthly_budget", "50")

                try:
                    budget = float(monthly_budget)
                except (TypeError, ValueError):
                    budget = 50.0

                if not api_key or not api_secret:
                    _set_config_message("error", "Porkbun API key and secret are required.")
                else:
                    domain_rotation_manager.set_api_client(PorkbunAPIClient(api_key, api_secret))
                    domain_rotation_manager.monthly_budget = budget
                    _set_config_message("success", "Domain API configured successfully.")

            else:
                # Backward-compatible lightweight session config storage.
                session["email_config"] = {
                    "smtp_server": request.form.get("smtp_server", ""),
                    "smtp_port": request.form.get("smtp_port", "587"),
                    "smtp_username": request.form.get("smtp_username", ""),
                    "imap_server": request.form.get("imap_server", ""),
                    "imap_port": request.form.get("imap_port", "993"),
                    "imap_username": request.form.get("imap_username", ""),
                }
                _set_config_message("success", "Configuration saved for this session.")

            return redirect(url_for('email_config', url_addition=url_addition))

        config = session.get('email_config', {})
        config_status = transport_manager.is_configured()
        budget_status = domain_rotation_manager.get_budget_status()
        active_domain = domain_rotation_manager.get_active_domain()

        return render_template("email_config.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              config=config,
                              config_status=config_status,
                              budget_status=budget_status,
                              active_domain=active_domain,
                              message=message)

    @app.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
    def email_domain_rotate(url_addition):
        """Rotate to a newly purchased cheap domain."""
        if url_addition != app.config["path"]:
            return ('', 404)

        new_domain = domain_rotation_manager.rotate_domain()
        if new_domain:
            burner_manager.set_custom_domain(new_domain)
            _set_config_message("success", f"Domain rotated successfully to {new_domain}.")
        else:
            _set_config_message(
                "error",
                "Domain rotation failed. Check API credentials, budget, and registrar availability."
            )

        return redirect(url_for('email_config', url_addition=url_addition))

    @app.route('/<string:url_addition>/email/receive', methods=["POST"])
    def email_receive(url_addition):
        """Fetch emails from configured IMAP transport into local inbox."""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session_user()

        if not transport_manager.is_configured().get("imap", False):
            _set_config_message("error", "IMAP is not configured yet.")
            return redirect(url_for('email_config', url_addition=url_addition))

        limit = _to_int(request.form.get("limit"), 10)
        unread_only = request.form.get("unread_only", "false").lower() == "true"
        limit = max(1, min(limit, 100))

        emails = transport_manager.receive_emails(limit=limit, unread_only=unread_only)
        for incoming_email in emails:
            email_storage.add_email(session["_id"], incoming_email)

        _set_config_message("success", f"Fetched {len(emails)} email(s) from IMAP.")
        return redirect(url_for('email_inbox', url_addition=url_addition))

    @app.route('/<string:url_addition>/email/compose', methods=["GET", "POST"])
    def email_compose(url_addition):
        """Email composition and sending with rate limiting"""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_session_user()
        smtp_configured = transport_manager.is_configured().get("smtp", False)
        send_limit_status = burner_manager.get_send_limit_status(session["_id"])

        if request.method == "POST":
            # Check rate limit before allowing send
            allowed, error_msg = burner_manager.check_send_rate_limit(session["_id"])

            if not allowed:
                return render_template("email_compose.html",
                                     hostname=app.config["hostname"],
                                     path=app.config["path"],
                                     error=error_msg,
                                     send_limit_status=send_limit_status,
                                     smtp_configured=smtp_configured)

            raw_mode = request.form.get("raw_mode", "false").lower() == "true"
            default_from = session.get("email_address", "anonymous@opsechat.onion")
            headers = {}

            if raw_mode:
                raw_email = request.form.get("raw_email", "").strip()
                if not raw_email:
                    return render_template("email_compose.html",
                                         hostname=app.config["hostname"],
                                         path=app.config["path"],
                                         error="Raw mode email cannot be empty.",
                                         send_limit_status=send_limit_status,
                                         smtp_configured=smtp_configured)

                parsed_email = EmailComposer.parse_raw_email(raw_email)
                from_addr = parsed_email.get("from", "").strip() or default_from
                to_addr = parsed_email.get("to", "").strip()
                subject = parsed_email.get("subject", "").strip()
                body = parsed_email.get("body", "").strip()
                raw_headers = parsed_email.get("headers", {})
                headers = {
                    EmailValidator.sanitize_header(str(key)): EmailValidator.sanitize_header(str(value))
                    for key, value in raw_headers.items()
                    if str(key).strip()
                }
            else:
                from_addr = request.form.get("from", "").strip() or default_from
                to_addr = request.form.get("to", "").strip()
                subject = request.form.get("subject", "").strip()
                body = request.form.get("body", "").strip()

            from_addr = EmailValidator.sanitize_header(from_addr)
            to_addr = EmailValidator.sanitize_header(to_addr)
            subject = EmailValidator.sanitize_header(subject)

            # Basic validation
            if not to_addr or not EmailValidator.validate_email_address(to_addr):
                return render_template("email_compose.html",
                                     hostname=app.config["hostname"],
                                     path=app.config["path"],
                                     error="Invalid recipient email address",
                                     send_limit_status=send_limit_status,
                                     smtp_configured=smtp_configured)

            if not EmailValidator.validate_email_address(from_addr):
                return render_template("email_compose.html",
                                     hostname=app.config["hostname"],
                                     path=app.config["path"],
                                     error="Invalid sender email address",
                                     send_limit_status=send_limit_status,
                                     smtp_configured=smtp_configured)

            if not body:
                return render_template("email_compose.html",
                                     hostname=app.config["hostname"],
                                     path=app.config["path"],
                                     error="Email body cannot be empty",
                                     send_limit_status=send_limit_status,
                                     smtp_configured=smtp_configured)

            smtp_requested = request.form.get("send_via_smtp", "false").lower() == "true"
            smtp_attempted = smtp_requested and smtp_configured
            smtp_success = False

            if smtp_requested and not smtp_configured:
                return render_template("email_compose.html",
                                     hostname=app.config["hostname"],
                                     path=app.config["path"],
                                     error="SMTP is not configured. Configure it in Email Configuration first.",
                                     send_limit_status=send_limit_status,
                                     smtp_configured=smtp_configured)

            if smtp_attempted:
                smtp_success = transport_manager.send_email(
                    from_addr=from_addr,
                    to_addr=to_addr,
                    subject=subject,
                    body=body,
                    headers=headers
                )

            email_data = EmailComposer.create_email(
                from_addr=from_addr,
                to_addr=to_addr,
                subject=subject,
                body=body,
                headers=headers
            )
            email_data.update({
                "raw_mode": raw_mode,
                "smtp_attempted": smtp_attempted,
                "sent_via_smtp": smtp_success,
                "sent": smtp_success or not smtp_requested
            })
            email_storage.add_email(session["_id"], email_data)

            # Record send after successful local persistence.
            burner_manager.record_sent_email(session["_id"])
            send_limit_status = burner_manager.get_send_limit_status(session["_id"])

            if smtp_requested and not smtp_success:
                return render_template("email_compose.html",
                                     hostname=app.config["hostname"],
                                     path=app.config["path"],
                                     error="SMTP delivery failed; message was saved locally only.",
                                     send_limit_status=send_limit_status,
                                     smtp_configured=smtp_configured)

            if smtp_success:
                success_message = "Email sent via SMTP and saved to your local inbox."
            else:
                success_message = "Email saved to your local inbox."

            return render_template("email_compose.html",
                                 hostname=app.config["hostname"],
                                 path=app.config["path"],
                                 success=success_message,
                                 send_limit_status=send_limit_status,
                                 smtp_configured=smtp_configured)

        # GET request - show compose form
        return render_template("email_compose.html",
                             hostname=app.config["hostname"],
                             path=app.config["path"],
                             send_limit_status=send_limit_status,
                             smtp_configured=smtp_configured)
