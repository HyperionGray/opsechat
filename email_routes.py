"""
Email system routes for opsechat.

This module is the production owner for:
- inbox/config/compose flows
- burner email management
- email security analysis/training pages
- admin-style send/receive/domain rotation actions
"""

from flask import render_template, request, session, jsonify, redirect, url_for

from email_system import email_storage, burner_manager, EmailComposer, EmailValidator
from email_security_tools import spoofing_tester, phishing_simulator
from email_transport import transport_manager
from domain_manager import domain_rotation_manager, PorkbunAPIClient


def register_email_routes(app, id_generator, get_random_color):
    """Register all email-related routes with the Flask app."""

    def _ensure_session():
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()

    def _require_path(url_addition):
        return url_addition == app.config["path"]

    def _config_status():
        return transport_manager.is_configured()

    def _template_email_config(message=None):
        return render_template(
            "email_config.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            message=message,
            config_status=_config_status(),
            budget_status=domain_rotation_manager.get_budget_status(),
            active_domain=domain_rotation_manager.get_active_domain(),
            transport_config=transport_manager.get_config(),
            domain_config=domain_rotation_manager.get_config(),
        )

    def _template_compose(**kwargs):
        defaults = {
            "hostname": app.config["hostname"],
            "path": app.config["path"],
            "smtp_configured": _config_status()["smtp"],
            "send_limit_status": burner_manager.get_send_limit_status(session["_id"]),
            "raw_email": "",
        }
        defaults.update(kwargs)
        return render_template("email_compose.html", **defaults)

    @app.route('/<string:url_addition>/email', methods=["GET"])
    def email_inbox(url_addition):
        """Main email inbox page."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        email_storage.create_user_inbox(session["_id"])
        emails = email_storage.get_emails(session["_id"])

        return render_template(
            "email_inbox.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            emails=emails,
            script_enabled=False,
        )

    @app.route('/<string:url_addition>/email/yesscript', methods=["GET"])
    def email_inbox_script(url_addition):
        """Email inbox with JavaScript enabled."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        email_storage.create_user_inbox(session["_id"])
        emails = email_storage.get_emails(session["_id"])

        return render_template(
            "email_inbox.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            emails=emails,
            script_enabled=True,
        )

    @app.route('/<string:url_addition>/email/burner', methods=["GET"])
    def email_burner(url_addition):
        """Burner email management page."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        burner_manager.cleanup_expired()
        active_burners = burner_manager.get_user_burners(session["_id"])

        return render_template(
            "email_burner.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            active_burners=active_burners,
            script_enabled=False,
        )

    @app.route('/<string:url_addition>/email/burner/yesscript', methods=["GET"])
    def email_burner_script(url_addition):
        """Burner email management with JavaScript."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        burner_manager.cleanup_expired()
        active_burners = burner_manager.get_user_burners(session["_id"])

        return render_template(
            "email_burner.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            active_burners=active_burners,
            script_enabled=True,
        )

    @app.route('/<string:url_addition>/email/burner/list', methods=["GET"])
    @app.route('/<string:url_addition>/email/burner/list.json', methods=["GET"])
    def email_burner_list_json(url_addition):
        """JSON API for burner email list."""
        if not _require_path(url_addition):
            return ('', 404)

        if "_id" not in session:
            return jsonify({"error": "No session"}), 401

        burner_manager.cleanup_expired()
        active_burners = burner_manager.get_user_burners(session["_id"])
        stats = burner_manager.get_user_stats(session["_id"])
        return jsonify({"burners": active_burners, "stats": stats})

    @app.route('/<string:url_addition>/email/config', methods=["GET", "POST"])
    def email_config(url_addition):
        """Email configuration page."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        message = None

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "configure_smtp":
                success = transport_manager.configure_smtp(
                    smtp_server=request.form.get("smtp_server", "").strip(),
                    smtp_port=int(request.form.get("smtp_port", 587)),
                    smtp_port=int(request.form.get("smtp_port") if request.form.get("smtp_port", "").isdigit() else 587),
                    password=request.form.get("smtp_password", "").strip(),
                    use_tls=request.form.get("use_tls") == "true" or request.form.get("use_tls") == "on",
                )
                message = {
                    "type": "success" if success else "error",
                    "text": "SMTP configuration saved successfully" if success else "SMTP configuration failed",
                }
            elif action == "configure_imap":
                success = transport_manager.configure_imap(
                    imap_server=request.form.get("imap_server", "").strip(),
                    imap_port=int(request.form.get("imap_port", 993)),
                    username=request.form.get("imap_username", "").strip(),
                    password=request.form.get("imap_password", "").strip(),
                    use_ssl=request.form.get("use_ssl") == "true" or request.form.get("use_ssl") == "on",
                )
                message = {
                    "type": "success" if success else "error",
                    "text": "IMAP configuration saved successfully" if success else "IMAP configuration failed",
                }
            elif action == "configure_domain_api":
                api_key = request.form.get("api_key", "").strip()
                api_secret = request.form.get("api_secret", "").strip()
                monthly_budget = float(request.form.get("monthly_budget", 50))
                if api_key and api_secret:
                    domain_rotation_manager.configure(
                        api_key=api_key,
                        secret_key=api_secret,
                        monthly_budget=monthly_budget,
                    )
                    message = {"type": "success", "text": "Domain API configuration saved successfully"}
                else:
                    message = {"type": "error", "text": "Domain API key and secret are required"}

        return _template_email_config(message=message)

    @app.route('/<string:url_addition>/email/compose', methods=["GET", "POST"])
    def email_compose(url_addition):
        """Email composition and sending with rate limiting."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()

        if request.method == "POST":
            allowed, error_msg = burner_manager.check_send_rate_limit(session["_id"])
            if not allowed:
                return _template_compose(error=error_msg)

            raw_mode = request.form.get("raw_mode") == "true"
            send_via_smtp = request.form.get("send_via_smtp") in {"true", "on"}

            if raw_mode:
                raw_email = request.form.get("raw_email", "").strip()
                if not raw_email:
                    return _template_compose(
                        error="Raw email content cannot be empty",
                        raw_email=raw_email,
                    )
                try:
                    email_data = EmailComposer.parse_raw_email(raw_email)
                except Exception:
                    return _template_compose(
                        error="Failed to parse raw email",
                        raw_email=raw_email,
                    )
            else:
                from_addr = request.form.get("from", "").strip() or session.get("email_address", "anonymous@opsechat.onion")
                to_addr = request.form.get("to", "").strip()
                subject = request.form.get("subject", "").strip()
                body = request.form.get("body", "").strip()

                if not to_addr or not EmailValidator.validate_email_address(to_addr):
                    return _template_compose(error="Invalid recipient email address")
                if from_addr and not EmailValidator.validate_email_address(from_addr):
                    return _template_compose(error="Invalid sender email address")
                if not body:
                    return _template_compose(error="Email body cannot be empty")

                email_data = EmailComposer.create_email(from_addr, to_addr, subject, body)

            send_result = False
            if send_via_smtp and transport_manager.is_configured()["smtp"]:
                send_result = transport_manager.send_email(
                    email_data.get("from", ""),
                    email_data.get("to", ""),
                    email_data.get("subject", ""),
                    email_data.get("body", ""),
                    email_data.get("headers", {}),
                )

            email_data["sent"] = send_result or not send_via_smtp
            email_storage.add_email(session["_id"], email_data)
            burner_manager.record_sent_email(session["_id"])

            success_message = "Email sent successfully"
            if send_via_smtp and not send_result:
                success_message = "Email saved locally, but SMTP sending failed"

            return _template_compose(success=success_message)

        return _template_compose()

    @app.route('/<string:url_addition>/email/view/<string:email_id>', methods=["GET"])
    def email_view(url_addition, email_id):
        """View a specific email."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        email = email_storage.get_email(session["_id"], email_id)
        if email is None:
            return render_template(
                "email_inbox.html",
                hostname=app.config["hostname"],
                path=app.config["path"],
                emails=email_storage.get_emails(session["_id"]),
                script_enabled=False,
                error="Email not found",
            ), 404

        return render_template(
            "email_view.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            email=email,
        )

    @app.route('/<string:url_addition>/email/edit/<string:email_id>', methods=["GET", "POST"])
    def email_edit(url_addition, email_id):
        """Edit an email in raw mode."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        email = email_storage.get_email(session["_id"], email_id)
        if email is None:
            return ('', 404)

        if request.method == "POST":
            raw_content = request.form.get("raw_email", "").strip()
            try:
                updated = EmailComposer.parse_raw_email(raw_content)
            except Exception:
                return render_template(
                    "email_edit.html",
                    hostname=app.config["hostname"],
                    path=app.config["path"],
                    email=email,
                    raw_email=raw_content,
                    error="Failed to parse email — check format",
                ), 400

            email_storage.update_email(session["_id"], email_id, updated)
            return redirect(url_for("email_view", url_addition=url_addition, email_id=email_id))

        raw_email = EmailComposer.format_raw_email(email)
        return render_template(
            "email_edit.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            email=email,
            raw_email=raw_email,
        )

    @app.route('/<string:url_addition>/email/delete/<string:email_id>', methods=["POST"])
    def email_delete(url_addition, email_id):
        """Delete a specific email."""
        if not _require_path(url_addition):
            return ('', 404)

        if "_id" not in session:
            return ('', 401)

        email_storage.delete_email(session["_id"], email_id)
        return redirect(url_for("email_inbox", url_addition=url_addition))

    @app.route('/<string:url_addition>/email/burner', methods=["POST"])
    def email_burner_post(url_addition):
        """Handle burner email generation and rotation."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        action = request.form.get("action", "generate")

        if action == "generate":
            burner_email = burner_manager.generate_burner_email(session["_id"])
            http_mail_storage.create_mailbox(owner_id=session["_id"], alias=burner_email)
        elif action == "rotate":
            old_email = request.form.get("old_email", "").strip() or None
            burner_manager.rotate_burner(session["_id"], old_email)

        return redirect(url_for("email_burner", url_addition=url_addition))

    @app.route('/<string:url_addition>/email/burner/expire/<path:burner_email>', methods=["POST"])
    def email_burner_expire(url_addition, burner_email):
        """Immediately expire a specific burner address."""
        if not _require_path(url_addition):
            return ('', 404)

        if "_id" not in session:
            return ('', 401)

        if burner_manager.get_user_for_burner(burner_email) == session["_id"]:
            burner_manager.expire_burner(burner_email)
        return redirect(url_for("email_burner", url_addition=url_addition))

    @app.route('/<string:url_addition>/email/security/spoof-test', methods=["GET", "POST"])
    def email_spoof_test(url_addition):
        """Spoofing test and variant generation page."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        results = None
        variants = None

        if request.method == "POST":
            test_type = request.form.get("test_type", "detect")
            if test_type == "detect":
                test_email = request.form.get("test_email", "").strip()
                legitimate_domain = request.form.get("legitimate_domain", "").strip()
                if test_email and legitimate_domain:
                    results = spoofing_tester.test_spoofing_detection(test_email, legitimate_domain)
            elif test_type == "generate":
                target_domain = request.form.get("target_domain", "").strip()
                if target_domain:
                    variants = spoofing_tester.generate_spoof_variants(target_domain)

        return render_template(
            "email_spoof_test.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            results=results,
            variants=variants,
            script_enabled=False,
        )

    @app.route('/<string:url_addition>/email/security/phishing-sim', methods=["GET", "POST"])
    def email_phishing_sim(url_addition):
        """Phishing simulation and training page."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        user_id = session["_id"]
        action_result = None

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            if action == "enable":
                phishing_simulator.enable_persist_mode(user_id)
            elif action == "disable":
                phishing_simulator.disable_persist_mode(user_id)
            elif action == "generate":
                template = request.form.get("template", "generic").strip() or "generic"
                phishing_email = phishing_simulator.create_phishing_email(user_id, template)
                email_storage.add_email(user_id, phishing_email)
                action_result = {
                    "type": "generated",
                    "message": "Phishing simulation email added to your inbox",
                }

        stats = phishing_simulator.get_user_stats(user_id)
        return render_template(
            "email_phishing_sim.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            stats=stats,
            action_result=action_result,
            script_enabled=False,
        )

    @app.route('/<string:url_addition>/email/send', methods=["POST"])
    def email_send_api(url_addition):
        """API endpoint for sending an email via configured SMTP."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        payload = request.get_json(silent=True) or request.form.to_dict()

        from_addr = (payload.get("from") or session.get("email_address") or "anonymous@opsechat.onion").strip()
        to_addr = (payload.get("to") or "").strip()
        subject = (payload.get("subject") or "").strip()
        body = (payload.get("body") or "").strip()

        if not to_addr or not EmailValidator.validate_email_address(to_addr):
            return jsonify({"success": False, "error": "Invalid recipient email address"}), 400
        if not body:
            return jsonify({"success": False, "error": "Email body cannot be empty"}), 400

        sent = transport_manager.send_email(from_addr, to_addr, subject, body)
        email_data = EmailComposer.create_email(from_addr, to_addr, subject, body)
        email_data["sent"] = sent
        email_storage.add_email(session["_id"], email_data)
        if sent:
            burner_manager.record_sent_email(session["_id"])

        return jsonify({
            "success": sent,
            "message": "Email sent successfully" if sent else "Failed to send email",
        }), (200 if sent else 500)

    @app.route('/<string:url_addition>/email/receive', methods=["POST"])
    def email_receive_api(url_addition):
        """API endpoint for receiving emails via configured IMAP."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        payload = request.get_json(silent=True) or request.form.to_dict()
        limit_raw = payload.get("limit")
        unread_only = payload.get("unread_only") in {"true", "True", "on", True}
        limit = int(limit_raw) if limit_raw not in (None, "") else None

        emails = transport_manager.receive_emails(limit=limit, unread_only=unread_only)
        for email_data in emails:
            email_storage.add_email(session["_id"], email_data)

        if request.is_json:
            return jsonify({"success": True, "emails": emails, "count": len(emails)})

        return redirect(url_for("email_inbox", url_addition=url_addition))

    @app.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
    def email_domain_rotate(url_addition):
        """Rotate to a new burner domain."""
        if not _require_path(url_addition):
            return ('', 404)

        _ensure_session()
        result = domain_rotation_manager.rotate_domain()
        if result.get("success") and result.get("active_domain"):
            burner_manager.set_custom_domain(result["active_domain"])

        if request.is_json:
            return jsonify(result), (200 if result.get("success") else 400)

        message = {
            "type": "success" if result.get("success") else "error",
            "text": result.get("message", "Domain rotation completed"),
        }
        return _template_email_config(message=message)
