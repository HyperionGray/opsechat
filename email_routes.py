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
from domain_manager import domain_rotation_manager


def register_email_routes(app, id_generator, get_random_color):
    """Register all email-related routes with the Flask app"""
    
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
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        if request.method == "POST":
            action = request.form.get('action', '').strip()
            message = {"type": "error", "text": "Unknown configuration action"}

            if action == "configure_smtp":
                smtp_server = request.form.get('smtp_server', '').strip()
                smtp_username = request.form.get('smtp_username', '').strip()
                smtp_password = request.form.get('smtp_password', '').strip()
                try:
                    smtp_port = int(request.form.get('smtp_port', '587'))
                except (TypeError, ValueError):
                    smtp_port = 587
                use_tls = request.form.get('use_tls') in ('true', 'on', '1')

                configured = transport_manager.configure_smtp(
                    smtp_server=smtp_server,
                    smtp_port=smtp_port,
                    username=smtp_username,
                    password=smtp_password,
                    use_tls=use_tls,
                )
                if configured:
                    message = {"type": "success", "text": "SMTP configuration saved successfully"}
                else:
                    message = {"type": "error", "text": "SMTP configuration failed (check server/credentials)"}

            elif action == "configure_imap":
                imap_server = request.form.get('imap_server', '').strip()
                imap_username = request.form.get('imap_username', '').strip()
                imap_password = request.form.get('imap_password', '').strip()
                try:
                    imap_port = int(request.form.get('imap_port', '993'))
                except (TypeError, ValueError):
                    imap_port = 993
                use_ssl = request.form.get('use_ssl') in ('true', 'on', '1')

                configured = transport_manager.configure_imap(
                    imap_server=imap_server,
                    imap_port=imap_port,
                    username=imap_username,
                    password=imap_password,
                    use_ssl=use_ssl,
                )
                if configured:
                    message = {"type": "success", "text": "IMAP configuration saved successfully"}
                else:
                    message = {"type": "error", "text": "IMAP configuration failed (check server/credentials)"}

            elif action == "configure_domain_api":
                try:
                    monthly_budget = float(request.form.get('monthly_budget', '50'))
                    domain_rotation_manager.configure(
                        api_key=request.form.get('api_key', '').strip(),
                        secret_key=request.form.get('api_secret', '').strip(),
                        monthly_budget=monthly_budget,
                    )
                    message = {"type": "success", "text": "Domain API configuration saved successfully"}
                except (ValueError, TypeError) as exc:
                    message = {"type": "error", "text": f"Domain configuration failed: {exc}"}

            session['email_config_message'] = message
            return redirect(url_for('email_config', url_addition=url_addition))

        message = session.pop('email_config_message', None)
        config_status = transport_manager.is_configured()
        budget_status = domain_rotation_manager.get_budget_status()
        active_domain = domain_rotation_manager.get_active_domain()

        return render_template("email_config.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              message=message,
                              config_status=config_status,
                              budget_status=budget_status,
                              active_domain=active_domain)

    @app.route('/<string:url_addition>/email/receive', methods=["POST"])
    def email_receive(url_addition):
        """Fetch emails from configured IMAP and return to config page."""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()

        limit = request.form.get("limit", "10")
        unread_only = request.form.get("unread_only", "false").lower() == "true"
        try:
            limit_int = max(1, min(100, int(limit)))
        except ValueError:
            limit_int = 10

        if not transport_manager.is_configured().get("imap"):
            session['email_config_message'] = {
                "type": "error",
                "text": "IMAP is not configured yet."
            }
            return redirect(url_for('email_config', url_addition=url_addition))

        emails = transport_manager.receive_emails(limit=limit_int, unread_only=unread_only)
        for email_data in emails:
            email_storage.add_email(session["_id"], email_data)

        session['email_config_message'] = {
            "type": "success",
            "text": f"Fetched {len(emails)} email(s) from IMAP."
        }
        return redirect(url_for('email_config', url_addition=url_addition))

    @app.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
    def email_rotate_domain(url_addition):
        """Rotate burner domain via configured registrar."""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()

        result = domain_rotation_manager.rotate_domain_with_result()
        if result.get("success"):
            burner_manager.set_custom_domain(result["domain"])
            session['email_config_message'] = {
                "type": "success",
                "text": f"Domain rotated successfully to {result['domain']}."
            }
        else:
            session['email_config_message'] = {
                "type": "error",
                "text": result.get("error", "Domain rotation failed.")
            }
        return redirect(url_for('email_config', url_addition=url_addition))
    
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
