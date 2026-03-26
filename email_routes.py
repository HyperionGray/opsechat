"""
Email system routes for opsechat

This module contains Flask routes for email functionality including:
- Email inbox management
- Email composition and sending
- Burner email system
- Email security tools (spoofing detection, phishing simulation)
- Email configuration management
"""

import logging
from flask import render_template, request, session, jsonify, redirect, url_for
from email_system import email_storage, burner_manager, EmailComposer, EmailValidator
from email_security_tools import spoofing_tester, phishing_simulator
from email_transport import transport_manager
from domain_manager import domain_rotation_manager


def register_email_routes(app, id_generator, get_random_color):
    """Register all email-related routes with the Flask app"""

    def _ensure_email_session():
        """Ensure stable per-user email session context."""
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
    
    @app.route('/<string:url_addition>/email', methods=["GET"])
    def email_inbox(url_addition):
        """Main email inbox page"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
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
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        email_storage.create_user_inbox(session["_id"])
        emails = email_storage.get_emails(session["_id"])
        
        return render_template("email_inbox.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              emails=emails,
                              script_enabled=True)

    @app.route('/<string:url_addition>/email/burner', methods=["GET"])
    def email_burner(url_addition):
        """Burner email management page"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        # Get active burner emails
        burner_emails = burner_manager.get_user_burners(session["_id"])
        
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              burner_emails=burner_emails,
                              script_enabled=False)

    @app.route('/<string:url_addition>/email/burner/yesscript', methods=["GET"])
    def email_burner_script(url_addition):
        """Burner email management with JavaScript"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        burner_emails = burner_manager.get_user_burners(session["_id"])
        
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              burner_emails=burner_emails,
                              script_enabled=True)

    @app.route('/<string:url_addition>/email/burner/list.json', methods=["GET"])
    def email_burner_list_json(url_addition):
        """JSON API for burner email list"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"error": "No session"}), 401
        
        burner_emails = burner_manager.get_user_burners(session["_id"])
        return jsonify({
            "burners": burner_emails,
            "stats": burner_manager.get_user_stats(session["_id"])
        })

    @app.route('/<string:url_addition>/email/config', methods=["GET", "POST"])
    def email_config(url_addition):
        """Email configuration page"""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_email_session()
        message = session.pop("email_config_message", None)

        if request.method == "POST":
            action = request.form.get("action", "")
            try:
                if action == "configure_smtp":
                    success = transport_manager.configure_smtp(
                        smtp_server=request.form.get("smtp_server", "").strip(),
                        smtp_port=int(request.form.get("smtp_port", "587")),
                        username=request.form.get("smtp_username", "").strip(),
                        password=request.form.get("smtp_password", ""),
                        use_tls=request.form.get("use_tls") in ("true", "on", "1"),
                    )
                    message = {
                        "type": "success" if success else "error",
                        "text": "SMTP configured successfully" if success else "SMTP configuration failed",
                    }
                elif action == "configure_imap":
                    success = transport_manager.configure_imap(
                        imap_server=request.form.get("imap_server", "").strip(),
                        imap_port=int(request.form.get("imap_port", "993")),
                        username=request.form.get("imap_username", "").strip(),
                        password=request.form.get("imap_password", ""),
                        use_ssl=request.form.get("use_ssl") in ("true", "on", "1"),
                    )
                    message = {
                        "type": "success" if success else "error",
                        "text": "IMAP configured successfully" if success else "IMAP configuration failed",
                    }
                elif action == "configure_domain_api":
                    configured = domain_rotation_manager.configure(
                        api_key=request.form.get("api_key", "").strip(),
                        api_secret=request.form.get("api_secret", "").strip(),
                        monthly_budget=float(request.form.get("monthly_budget", "50")),
                    )
                    message = {
                        "type": "success" if configured.get("success") else "error",
                        "text": (
                            "Domain API configured successfully"
                            if configured.get("success")
                            else f"Domain API configuration failed: {configured.get('error', 'unknown error')}"
                        ),
                    }
                elif action:
                    message = {"type": "error", "text": f"Unknown configuration action: {action}"}
            except Exception as exc:
                logging.exception("Failed email config action")
                message = {"type": "error", "text": f"Configuration failed: {exc}"}

        config_status = transport_manager.is_configured()
        budget_status = domain_rotation_manager.get_budget_status()
        active_domain = domain_rotation_manager.get_active_domain()

        return render_template("email_config.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              message=message,
                              config_status=config_status,
                              active_domain=active_domain,
                              budget_status=budget_status)

    @app.route('/<string:url_addition>/email/receive', methods=["POST"])
    def email_receive(url_addition):
        """Fetch emails from configured IMAP transport into the local inbox."""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_email_session()
        try:
            limit = int(request.form.get("limit", "10"))
        except ValueError:
            limit = 10
        limit = max(1, min(limit, 100))
        unread_only = request.form.get("unread_only", "false").lower() in ("true", "1", "on")

        received = transport_manager.receive_emails(limit=limit, unread_only=unread_only)
        for email_data in received:
            email_storage.add_email(session["_id"], email_data)

        session["email_config_message"] = {
            "type": "success",
            "text": f"Fetched {len(received)} emails from IMAP",
        }
        return redirect(url_for("email_config", url_addition=url_addition))

    @app.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
    def email_domain_rotate(url_addition):
        """Rotate domain and wire new domain to burner email generation."""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_email_session()
        result = domain_rotation_manager.rotate_to_new_domain()
        if result.get("success"):
            burner_manager.set_custom_domain(result["domain"])
            session["email_config_message"] = {
                "type": "success",
                "text": (
                    f"Rotated domain to {result['domain']} "
                    f"via provider {result.get('provider', 'unknown')}"
                ),
            }
        else:
            session["email_config_message"] = {
                "type": "error",
                "text": f"Domain rotation failed: {result.get('error', 'unknown error')}",
            }
        return redirect(url_for("email_config", url_addition=url_addition))
    
    @app.route('/<string:url_addition>/email/compose', methods=["GET", "POST"])
    def email_compose(url_addition):
        """Email composition and sending with rate limiting"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        if request.method == "POST":
            # Check rate limit before allowing send
            allowed, error_msg = burner_manager.check_send_rate_limit(session["_id"])
            
            if not allowed:
                return render_template("email_compose.html",
                                     hostname=app.config["hostname"],
                                     path=app.config["path"],
                                     error=error_msg,
                                     send_limit_status=burner_manager.get_send_limit_status(session["_id"]))
            
            # Get form data
            to_addr = request.form.get('to', '').strip()
            subject = request.form.get('subject', '').strip()
            body = request.form.get('body', '').strip()
            
            # Basic validation
            if not to_addr or not EmailValidator.validate_email_address(to_addr):
                return render_template("email_compose.html",
                                     hostname=app.config["hostname"],
                                     path=app.config["path"],
                                     error="Invalid recipient email address",
                                     send_limit_status=burner_manager.get_send_limit_status(session["_id"]))
            
            if not body:
                return render_template("email_compose.html",
                                     hostname=app.config["hostname"],
                                     path=app.config["path"],
                                     error="Email body cannot be empty",
                                     send_limit_status=burner_manager.get_send_limit_status(session["_id"]))
            
            # Record the send (for rate limiting)
            burner_manager.record_sent_email(session["_id"])
            
            # In a real implementation, this would use transport_manager to send
            # For now, just store in local inbox as sent
            email_data = {
                'to': to_addr,
                'from': session.get('email_address', 'anonymous@opsechat.onion'),
                'subject': subject,
                'body': body,
                'sent': True
            }
            email_storage.add_email(session["_id"], email_data)
            
            return render_template("email_compose.html",
                                 hostname=app.config["hostname"],
                                 path=app.config["path"],
                                 success="Email sent successfully",
                                 send_limit_status=burner_manager.get_send_limit_status(session["_id"]))
        
        # GET request - show compose form
        return render_template("email_compose.html",
                             hostname=app.config["hostname"],
                             path=app.config["path"],
                             send_limit_status=burner_manager.get_send_limit_status(session["_id"]))

    # ------------------------------------------------------------------
    # View a single email
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/email/view/<string:email_id>', methods=["GET"])
    def email_view(url_addition, email_id):
        """View a specific email"""
        if url_addition != app.config["path"]:
            return ('', 404)

        _ensure_email_session()

        email = email_storage.get_email(session["_id"], email_id)
        if email is None:
            return render_template("email_inbox.html",
                                   hostname=app.config["hostname"],
                                   path=app.config["path"],
                                   emails=email_storage.get_emails(session["_id"]),
                                   script_enabled=False,
                                   error="Email not found"), 404

        return render_template("email_view.html",
                               hostname=app.config["hostname"],
                               path=app.config["path"],
                               email=email)

    # ------------------------------------------------------------------
    # Edit a single email (raw mode)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/email/edit/<string:email_id>',
               methods=["GET", "POST"])
    def email_edit(url_addition, email_id):
        """Edit an email in raw mode"""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()

        email = email_storage.get_email(session["_id"], email_id)
        if email is None:
            return ('', 404)

        if request.method == "POST":
            raw_content = request.form.get("raw_email", "").strip()
            try:
                updated = EmailComposer.parse_raw_email(raw_content)
            except Exception:
                return render_template("email_edit.html",
                                       hostname=app.config["hostname"],
                                       path=app.config["path"],
                                       email=email,
                                       raw_email=raw_content,
                                       error="Failed to parse email — check format"), 400
            email_storage.update_email(session["_id"], email_id, updated)
            return redirect(url_for("email_view",
                                    url_addition=url_addition,
                                    email_id=email_id))

        # GET — render editor with current raw content
        raw_email = EmailComposer.format_raw_email(email)
        return render_template("email_edit.html",
                               hostname=app.config["hostname"],
                               path=app.config["path"],
                               email=email,
                               raw_email=raw_email)

    # ------------------------------------------------------------------
    # Delete a single email
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/email/delete/<string:email_id>',
               methods=["POST"])
    def email_delete(url_addition, email_id):
        """Delete a specific email"""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            return ('', 401)

        email_storage.delete_email(session["_id"], email_id)
        return redirect(url_for("email_inbox", url_addition=url_addition))

    # ------------------------------------------------------------------
    # Burner email POST actions (generate / rotate)
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/email/burner', methods=["POST"])
    def email_burner_post(url_addition):
        """Handle burner email generation and rotation"""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()

        action = request.form.get("action", "generate")

        if action == "generate":
            burner_manager.generate_burner_email(session["_id"])
        elif action == "rotate":
            old_email = request.form.get("old_email", "")
            burner_manager.rotate_burner(session["_id"], old_email or None)

        return redirect(url_for("email_burner", url_addition=url_addition))

    # ------------------------------------------------------------------
    # Expire (immediately delete) a specific burner address
    # ------------------------------------------------------------------

    @app.route('/<string:url_addition>/email/burner/expire/<path:burner_email>',
               methods=["POST"])
    def email_burner_expire(url_addition, burner_email):
        """Immediately expire a burner email address"""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            return ('', 401)

        burner_manager.expire_burner(burner_email)
        return redirect(url_for("email_burner", url_addition=url_addition))
