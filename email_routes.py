"""
Email system routes for opsechat.
"""

from typing import Any, Dict, Optional

from flask import jsonify, redirect, render_template, request, session, url_for

from domain_manager import PorkbunAPIClient, domain_rotation_manager
from email_security_tools import phishing_simulator, spoofing_tester
from email_system import EmailComposer, EmailValidator, burner_manager, email_storage
from email_transport import IMAPTransport, SMTPTransport


runtime_email_configs: Dict[str, Dict[str, Any]] = {}


def register_email_routes(app, id_generator, get_random_color):
    """Register all email-related routes with the Flask app."""

    def _path_ok(url_addition: str) -> bool:
        return url_addition == app.config["path"]

    def _parse_bool(value: Any) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _parse_int(
        value: Any, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    def _parse_float(
        value: Any, default: float, minimum: Optional[float] = None, maximum: Optional[float] = None
    ) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = default
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    def _ensure_session_user() -> str:
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        user_id = session["_id"]
        email_storage.create_user_inbox(user_id)
        return user_id

    def _get_user_config(user_id: str) -> Dict[str, Any]:
        if user_id not in runtime_email_configs:
            runtime_email_configs[user_id] = {}
        return runtime_email_configs[user_id]

    def _smtp_configured(config: Dict[str, Any]) -> bool:
        required = ["smtp_server", "smtp_port", "smtp_username", "smtp_password"]
        return all(config.get(key) for key in required)

    def _imap_configured(config: Dict[str, Any]) -> bool:
        required = ["imap_server", "imap_port", "imap_username", "imap_password"]
        return all(config.get(key) for key in required)

    def _render_compose(url_addition: str, **kwargs):
        user_id = _ensure_session_user()
        config = _get_user_config(user_id)
        kwargs.setdefault("smtp_configured", _smtp_configured(config))
        kwargs.setdefault("default_from", session.get("email_address", "anonymous@opsechat.onion"))
        kwargs.setdefault("send_limit_status", burner_manager.get_send_limit_status(user_id))
        return render_template(
            "email_compose.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            **kwargs,
        )

    @app.route('/<string:url_addition>/email', methods=["GET"])
    def email_inbox(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        emails = email_storage.get_emails(user_id)
        return render_template(
            "email_inbox.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            emails=emails,
            script_enabled=False,
            message=request.args.get("message"),
            error=request.args.get("error"),
        )

    @app.route('/<string:url_addition>/email/yesscript', methods=["GET"])
    def email_inbox_script(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        emails = email_storage.get_emails(user_id)
        return render_template(
            "email_inbox.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            emails=emails,
            script_enabled=True,
            message=request.args.get("message"),
            error=request.args.get("error"),
        )

    @app.route('/<string:url_addition>/email/burner', methods=["GET", "POST"])
    def email_burner(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        message = None
        error = None

        if request.method == "POST":
            action = request.form.get("action", "generate")
            if action == "rotate":
                old_email = request.form.get("old_email", "").strip()
                burner_email = burner_manager.rotate_burner(user_id, old_email=old_email or None)
                message = "Burner rotated successfully"
            else:
                burner_email = burner_manager.generate_burner_email(user_id)
                message = "Burner generated successfully"

            session["email_address"] = burner_email

        active_burners = burner_manager.get_user_burners(user_id)
        return render_template(
            "email_burner.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            active_burners=active_burners,
            burner_emails=active_burners,
            script_enabled=False,
            message=message,
            error=error,
        )

    @app.route('/<string:url_addition>/email/burner/yesscript', methods=["GET"])
    def email_burner_script(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        active_burners = burner_manager.get_user_burners(user_id)
        return render_template(
            "email_burner.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            active_burners=active_burners,
            burner_emails=active_burners,
            script_enabled=True,
            message=request.args.get("message"),
            error=request.args.get("error"),
        )

    @app.route('/<string:url_addition>/email/burner/expire/<path:burner_email>', methods=["POST"])
    def email_burner_expire(url_addition, burner_email):
        if not _path_ok(url_addition):
            return ('', 404)
        _ensure_session_user()
        burner_manager.expire_burner(burner_email)
        return redirect(url_for("email_burner", url_addition=url_addition))

    @app.route('/<string:url_addition>/email/burner/list', methods=["GET"])
    @app.route('/<string:url_addition>/email/burner/list.json', methods=["GET"])
    def email_burner_list_json(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        burners = burner_manager.get_user_burners(user_id)
        return jsonify(
            {
                "burners": burners,
                "stats": {
                    "active_burners": len(burners),
                    "send_limit": burner_manager.get_send_limit_status(user_id),
                },
            }
        )

    @app.route('/<string:url_addition>/email/config', methods=["GET", "POST"])
    def email_config(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        config = _get_user_config(user_id)
        message = None

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "configure_smtp":
                smtp_server = request.form.get("smtp_server", "").strip()
                smtp_port = _parse_int(request.form.get("smtp_port"), 587, minimum=1, maximum=65535)
                smtp_username = request.form.get("smtp_username", "").strip()
                smtp_password = request.form.get("smtp_password", "").strip()
                use_tls = _parse_bool(request.form.get("use_tls"))
                smtp_retries = _parse_int(request.form.get("smtp_retries"), 3, minimum=1, maximum=5)
                smtp_backoff_seconds = _parse_float(
                    request.form.get("smtp_backoff_seconds"), 1.0, minimum=0.0, maximum=30.0
                )

                if not (smtp_server and smtp_username and smtp_password):
                    message = {"type": "error", "text": "SMTP configuration requires server, username, and password."}
                else:
                    transport = SMTPTransport(
                        smtp_server=smtp_server,
                        smtp_port=smtp_port,
                        username=smtp_username,
                        password=smtp_password,
                        use_tls=use_tls,
                    )
                    if transport.test_connection():
                        config.update(
                            {
                                "smtp_server": smtp_server,
                                "smtp_port": smtp_port,
                                "smtp_username": smtp_username,
                                "smtp_password": smtp_password,
                                "smtp_use_tls": use_tls,
                                "smtp_retries": smtp_retries,
                                "smtp_backoff_seconds": smtp_backoff_seconds,
                            }
                        )
                        message = {"type": "success", "text": "SMTP configuration saved and verified."}
                    else:
                        message = {"type": "error", "text": "SMTP connection test failed. Configuration not saved."}

            elif action == "configure_imap":
                imap_server = request.form.get("imap_server", "").strip()
                imap_port = _parse_int(request.form.get("imap_port"), 993, minimum=1, maximum=65535)
                imap_username = request.form.get("imap_username", "").strip()
                imap_password = request.form.get("imap_password", "").strip()
                use_ssl = _parse_bool(request.form.get("use_ssl"))

                if not (imap_server and imap_username and imap_password):
                    message = {"type": "error", "text": "IMAP configuration requires server, username, and password."}
                else:
                    transport = IMAPTransport(
                        imap_server=imap_server,
                        imap_port=imap_port,
                        username=imap_username,
                        password=imap_password,
                        use_ssl=use_ssl,
                    )
                    if transport.test_connection():
                        config.update(
                            {
                                "imap_server": imap_server,
                                "imap_port": imap_port,
                                "imap_username": imap_username,
                                "imap_password": imap_password,
                                "imap_use_ssl": use_ssl,
                            }
                        )
                        message = {"type": "success", "text": "IMAP configuration saved and verified."}
                    else:
                        message = {"type": "error", "text": "IMAP connection test failed. Configuration not saved."}

            elif action == "configure_domain_api":
                api_key = request.form.get("api_key", "").strip()
                api_secret = request.form.get("api_secret", "").strip()
                monthly_budget = _parse_float(request.form.get("monthly_budget"), 50.0, minimum=1.0)
                if not (api_key and api_secret):
                    message = {"type": "error", "text": "Domain API configuration requires API key and secret."}
                else:
                    domain_rotation_manager.set_api_client(PorkbunAPIClient(api_key=api_key, api_secret=api_secret))
                    domain_rotation_manager.monthly_budget = monthly_budget
                    message = {"type": "success", "text": "Domain API configuration updated."}

        config_status = {"smtp": _smtp_configured(config), "imap": _imap_configured(config)}
        return render_template(
            "email_config.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            message=message,
            config=config,
            config_status=config_status,
            active_domain=domain_rotation_manager.get_active_domain(),
            budget_status=domain_rotation_manager.get_budget_status(),
        )

    @app.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
    def email_rotate_domain(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        _ensure_session_user()
        new_domain = domain_rotation_manager.rotate_domain()
        if new_domain:
            burner_manager.set_custom_domain(new_domain)
            return redirect(url_for("email_config", url_addition=url_addition))
        return redirect(url_for("email_config", url_addition=url_addition))

    @app.route('/<string:url_addition>/email/receive', methods=["POST"])
    def email_receive(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        config = _get_user_config(user_id)
        if not _imap_configured(config):
            return redirect(
                url_for(
                    "email_inbox",
                    url_addition=url_addition,
                    error="IMAP is not configured.",
                )
            )

        limit = _parse_int(request.form.get("limit"), 10, minimum=1, maximum=100)
        unread_only = _parse_bool(request.form.get("unread_only"))
        transport = IMAPTransport(
            imap_server=str(config["imap_server"]),
            imap_port=int(config["imap_port"]),
            username=str(config["imap_username"]),
            password=str(config["imap_password"]),
            use_ssl=bool(config.get("imap_use_ssl", True)),
        )
        emails = transport.fetch_emails(limit=limit, unread_only=unread_only)
        for incoming in emails:
            email_storage.add_email(user_id, incoming)

        return redirect(
            url_for(
                "email_inbox",
                url_addition=url_addition,
                message=f"Fetched {len(emails)} email(s).",
            )
        )

    @app.route('/<string:url_addition>/email/compose', methods=["GET", "POST"])
    def email_compose(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)

        user_id = _ensure_session_user()
        config = _get_user_config(user_id)
        smtp_is_configured = _smtp_configured(config)

        if request.method == "POST":
            allowed, error_msg = burner_manager.check_send_rate_limit(user_id)
            if not allowed:
                return _render_compose(url_addition, error=error_msg)

            raw_mode = _parse_bool(request.form.get("raw_mode"))
            headers = {}

            if raw_mode:
                raw_email = request.form.get("raw_email", "").strip()
                if not raw_email:
                    return _render_compose(url_addition, error="Raw email content cannot be empty.")
                parsed = EmailComposer.parse_raw_email(raw_email)
                from_addr = parsed.get("from", "").strip()
                to_addr = parsed.get("to", "").strip()
                subject = parsed.get("subject", "").strip()
                body = parsed.get("body", "").strip()
                headers = parsed.get("headers", {})
            else:
                from_addr = request.form.get("from", "").strip()
                to_addr = request.form.get("to", "").strip()
                subject = request.form.get("subject", "").strip()
                body = request.form.get("body", "").strip()

            if not from_addr:
                from_addr = session.get("email_address", "anonymous@opsechat.onion")

            if not EmailValidator.validate_email_address(from_addr):
                return _render_compose(url_addition, error="Invalid sender email address.")
            if not to_addr or not EmailValidator.validate_email_address(to_addr):
                return _render_compose(url_addition, error="Invalid recipient email address.")
            if not body:
                return _render_compose(url_addition, error="Email body cannot be empty.")

            send_via_smtp = _parse_bool(request.form.get("send_via_smtp"))

            burner_manager.record_sent_email(user_id)

            smtp_sent = False
            if send_via_smtp:
                if not smtp_is_configured:
                    return _render_compose(url_addition, error="SMTP is not configured.")

                smtp_transport = SMTPTransport(
                    smtp_server=str(config["smtp_server"]),
                    smtp_port=int(config["smtp_port"]),
                    username=str(config["smtp_username"]),
                    password=str(config["smtp_password"]),
                    use_tls=bool(config.get("smtp_use_tls", True)),
                    max_retries=int(config.get("smtp_retries", 3)),
                    retry_backoff_seconds=float(config.get("smtp_backoff_seconds", 1.0)),
                )
                smtp_sent = smtp_transport.send_email(
                    from_addr=from_addr,
                    to_addr=to_addr,
                    subject=subject,
                    body=body,
                    headers=headers,
                )
                if not smtp_sent:
                    return _render_compose(
                        url_addition,
                        error="SMTP delivery failed after retries. Message was not sent to remote server.",
                    )

            email_data = EmailComposer.create_email(
                from_addr=from_addr,
                to_addr=to_addr,
                subject=subject,
                body=body,
                headers=headers,
            )
            email_data["sent"] = True
            email_data["smtp_sent"] = smtp_sent
            email_storage.add_email(user_id, email_data)

            success_msg = "Email sent successfully via SMTP." if smtp_sent else "Email saved to local inbox."
            return _render_compose(url_addition, success=success_msg)

        return _render_compose(url_addition)

    @app.route('/<string:url_addition>/email/view/<string:email_id>', methods=["GET"])
    def email_view(url_addition, email_id):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        email_data = email_storage.get_email(user_id, email_id)
        if not email_data:
            return ('', 404)
        return render_template(
            "email_view.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            email=email_data,
        )

    @app.route('/<string:url_addition>/email/edit/<string:email_id>', methods=["GET", "POST"])
    def email_edit(url_addition, email_id):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        email_data = email_storage.get_email(user_id, email_id)
        if not email_data:
            return ('', 404)

        if request.method == "POST":
            raw_email = request.form.get("raw_email", "").strip()
            parsed_email = EmailComposer.parse_raw_email(raw_email)
            if not parsed_email.get("from") or not parsed_email.get("to"):
                return render_template(
                    "email_edit.html",
                    hostname=app.config["hostname"],
                    path=app.config["path"],
                    email=email_data,
                    raw_email=raw_email,
                    error="From and To headers are required.",
                )
            email_storage.update_email(user_id, email_id, parsed_email)
            return redirect(url_for("email_view", url_addition=url_addition, email_id=email_id))

        raw_email = EmailComposer.format_raw_email(email_data)
        return render_template(
            "email_edit.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            email=email_data,
            raw_email=raw_email,
        )

    @app.route('/<string:url_addition>/email/delete/<string:email_id>', methods=["POST"])
    def email_delete(url_addition, email_id):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()
        existing_email = email_storage.get_email(user_id, email_id)
        deleted = email_storage.delete_email(user_id, email_id)
        if existing_email and existing_email.get("is_phishing_sim"):
            phishing_simulator.record_user_action(user_id, email_id, "deleted")

        if deleted:
            return redirect(url_for("email_inbox", url_addition=url_addition, message="Email deleted."))
        return redirect(url_for("email_inbox", url_addition=url_addition, error="Email not found."))

    @app.route('/<string:url_addition>/email/security/spoof-test', methods=["GET", "POST"])
    def email_spoof_test(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        _ensure_session_user()

        results = None
        variants = None
        if request.method == "POST":
            test_type = request.form.get("test_type", "detect")
            if test_type == "generate":
                target_domain = request.form.get("target_domain", "").strip()
                if target_domain:
                    variants = spoofing_tester.generate_spoof_variants(target_domain)
            else:
                test_email = request.form.get("test_email", "").strip()
                legitimate_domain = request.form.get("legitimate_domain", "").strip()
                if test_email and legitimate_domain:
                    results = spoofing_tester.test_spoofing_detection(test_email, legitimate_domain)

        return render_template(
            "email_spoof_test.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            results=results,
            variants=variants,
        )

    @app.route('/<string:url_addition>/email/security/phishing-sim', methods=["GET", "POST"])
    def email_phishing_sim(url_addition):
        if not _path_ok(url_addition):
            return ('', 404)
        user_id = _ensure_session_user()

        action_result = None
        if request.method == "POST":
            action = request.form.get("action", "").strip()
            if action == "enable":
                phishing_simulator.enable_persist_mode(user_id)
                action_result = {"message": "Persist mode enabled."}
            elif action == "disable":
                phishing_simulator.disable_persist_mode(user_id)
                action_result = {"message": "Persist mode disabled."}
            elif action == "generate":
                template = request.form.get("template", "generic").strip() or "generic"
                phishing_email = phishing_simulator.create_phishing_email(user_id, template=template)
                email_storage.add_email(user_id, phishing_email)
                action_result = {"message": f"Generated phishing simulation email ({template})."}

        stats = phishing_simulator.get_user_stats(user_id)
        return render_template(
            "email_phishing_sim.html",
            hostname=app.config["hostname"],
            path=app.config["path"],
            stats=stats,
            action_result=action_result,
        )
