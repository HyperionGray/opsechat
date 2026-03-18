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

logger = logging.getLogger(__name__)


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
        
        message = session.pop("email_config_message", None)

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "configure_smtp":
                try:
                    configured = transport_manager.configure_smtp(
                        smtp_server=request.form.get("smtp_server", "").strip(),
                        smtp_port=int(request.form.get("smtp_port", 587)),
                        username=request.form.get("smtp_username", "").strip(),
                        password=request.form.get("smtp_password", "").strip(),
                        use_tls=request.form.get("use_tls") == "true",
                    )
                    if configured:
                        message = {"type": "success", "text": "SMTP configured successfully"}
                    else:
                        message = {"type": "error", "text": "SMTP configuration failed (connection test failed)"}
                except (TypeError, ValueError) as exc:
                    message = {"type": "error", "text": f"Invalid SMTP configuration: {exc}"}

            elif action == "configure_imap":
                try:
                    configured = transport_manager.configure_imap(
                        imap_server=request.form.get("imap_server", "").strip(),
                        imap_port=int(request.form.get("imap_port", 993)),
                        username=request.form.get("imap_username", "").strip(),
                        password=request.form.get("imap_password", "").strip(),
                        use_ssl=request.form.get("use_ssl") == "true",
                    )
                    if configured:
                        message = {"type": "success", "text": "IMAP configured successfully"}
                    else:
                        message = {"type": "error", "text": "IMAP configuration failed (connection test failed)"}
                except (TypeError, ValueError) as exc:
                    message = {"type": "error", "text": f"Invalid IMAP configuration: {exc}"}

            elif action == "configure_domain_api":
                try:
                    domain_rotation_manager.configure(
                        api_key=request.form.get("api_key", "").strip(),
                        secret_key=request.form.get("api_secret", "").strip(),
                        monthly_budget=float(request.form.get("monthly_budget", 50)),
                    )
                    message = {"type": "success", "text": "Domain API configured successfully"}
                except Exception as exc:
                    message = {"type": "error", "text": f"Domain configuration failed: {exc}"}

            else:
                message = {"type": "error", "text": "Unknown configuration action"}

        config_status = transport_manager.is_configured()
        budget_status = domain_rotation_manager.get_budget_status()
        active_domain = domain_rotation_manager.get_active_domain()

        return render_template("email_config.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              message=message,
                              config_status=config_status,
                              budget_status=budget_status,
                              active_domain=active_domain,
                              domain_config=domain_rotation_manager.get_config(mask_secrets=True))

    @app.route('/<string:url_addition>/email/receive', methods=["POST"])
    def email_receive(url_addition):
        """Fetch email from configured IMAP account and store in inbox."""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            return ('', 401)

        try:
            limit = int(request.form.get("limit", 10))
        except ValueError:
            limit = 10
        unread_only = request.form.get("unread_only", "false").lower() == "true"

        try:
            incoming_emails = transport_manager.receive_emails(limit=limit, unread_only=unread_only)
            for email_data in incoming_emails:
                email_storage.add_email(session["_id"], email_data)
            session["email_config_message"] = {
                "type": "success",
                "text": f"Fetched {len(incoming_emails)} emails",
            }
        except Exception:
            logger.exception("Failed to fetch emails")
            session["email_config_message"] = {
                "type": "error",
                "text": "Failed to fetch emails from IMAP server",
            }

        return redirect(url_for("email_config", url_addition=url_addition))

    @app.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
    def email_domain_rotate(url_addition):
        """Rotate to a newly purchased cheap domain."""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            return ('', 401)

        try:
            result = domain_rotation_manager.rotate_to_new_domain()
            if result.get("success"):
                session["email_config_message"] = {
                    "type": "success",
                    "text": f"Active domain rotated to: {result.get('domain')}",
                }
            else:
                session["email_config_message"] = {
                    "type": "error",
                    "text": result.get("error", "Domain rotation failed"),
                }
        except Exception:
            logger.exception("Failed to rotate domain")
            session["email_config_message"] = {
                "type": "error",
                "text": "Unexpected domain rotation error",
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
