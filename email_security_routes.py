# Email Security and Configuration Routes
from flask import Blueprint, render_template, jsonify, request, session
from email_security_tools import spoofing_tester, phishing_simulator
from email_transport import transport_manager
from domain_manager import domain_rotation_manager
from email_system import EmailComposer, email_storage
import logging

def create_email_security_blueprint(id_generator, get_random_color):
    """Create and configure the email security routes blueprint"""
    
    email_security_bp = Blueprint('email_security', __name__)

    def _form_bool(value, default=False):
        """Convert HTML form checkbox-like values to bool."""
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @email_security_bp.route('/<string:url_addition>/email/security/spoof-test', methods=["GET", "POST"])
    def email_spoof_test(url_addition):
        """Email spoofing detection test"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        result = None
        
        if request.method == "POST":
            test_email = request.form.get("test_email", "").strip()
            if test_email:
                try:
                    result = spoofing_tester.analyze_email(test_email)
                except Exception as e:
                    result = {"error": f"Analysis failed: {str(e)}"}
        
        return render_template("email_spoof_test.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              result=result)

    @email_security_bp.route('/<string:url_addition>/email/security/phishing-sim', methods=["GET", "POST"])
    def email_phishing_sim(url_addition):
        """Phishing simulation and training"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        result = None
        
        if request.method == "POST":
            action = request.form.get("action")
            
            if action == "analyze":
                email_content = request.form.get("email_content", "").strip()
                if email_content:
                    try:
                        result = phishing_simulator.analyze_email(email_content)
                    except Exception as e:
                        result = {"error": f"Analysis failed: {str(e)}"}
            elif action == "generate":
                try:
                    result = phishing_simulator.generate_training_email()
                except Exception as e:
                    result = {"error": f"Generation failed: {str(e)}"}
        
        return render_template("email_phishing_sim.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              result=result)

    @email_security_bp.route('/<string:url_addition>/email/config', methods=["GET", "POST"])
    def email_config(url_addition):
        """Email configuration page"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        message = None
        config_status = transport_manager.is_configured()
        domain_config = domain_rotation_manager.get_config()
        budget_status = domain_rotation_manager.get_budget_status()
        active_domain = domain_rotation_manager.get_active_domain()
        
        if request.method == "POST":
            action = request.form.get("action") or request.form.get("config_type")

            if action in {"configure_smtp", "smtp"}:
                try:
                    smtp_server = request.form.get("smtp_server", "").strip()
                    smtp_port = int(request.form.get("smtp_port", 587))
                    username = request.form.get("smtp_username") or request.form.get("username", "")
                    password = request.form.get("smtp_password") or request.form.get("password", "")
                    use_tls = _form_bool(request.form.get("use_tls"), default=True)

                    success = transport_manager.configure_smtp(
                        smtp_server=smtp_server,
                        smtp_port=smtp_port,
                        username=username.strip(),
                        password=password.strip(),
                        use_tls=use_tls
                    )
                    if success:
                        message = {"type": "success", "text": "SMTP configuration saved successfully"}
                    else:
                        message = {"type": "error", "text": "SMTP configuration failed. Check credentials/server settings."}
                except Exception as e:
                    message = {"type": "error", "text": f"SMTP configuration failed: {str(e)}"}
            
            elif action in {"configure_imap", "imap"}:
                try:
                    imap_server = request.form.get("imap_server", "").strip()
                    imap_port = int(request.form.get("imap_port", 993))
                    username = request.form.get("imap_username") or request.form.get("username", "")
                    password = request.form.get("imap_password") or request.form.get("password", "")
                    use_ssl = _form_bool(request.form.get("use_ssl"), default=True)

                    success = transport_manager.configure_imap(
                        imap_server=imap_server,
                        imap_port=imap_port,
                        username=username.strip(),
                        password=password.strip(),
                        use_ssl=use_ssl
                    )
                    if success:
                        message = {"type": "success", "text": "IMAP configuration saved successfully"}
                    else:
                        message = {"type": "error", "text": "IMAP configuration failed. Check credentials/server settings."}
                except Exception as e:
                    message = {"type": "error", "text": f"IMAP configuration failed: {str(e)}"}
            
            elif action in {"configure_domain_api", "domain"}:
                try:
                    api_key = request.form.get("api_key") or request.form.get("porkbun_api_key", "")
                    api_secret = request.form.get("api_secret") or request.form.get("porkbun_secret_key", "")
                    monthly_budget = float(request.form.get("monthly_budget", 10.0))
                    config_result = domain_rotation_manager.configure(
                        api_key=api_key.strip(),
                        secret_key=api_secret.strip(),
                        monthly_budget=monthly_budget
                    )
                    if config_result.get("success"):
                        message = {"type": "success", "text": "Domain configuration saved successfully"}
                    else:
                        message = {"type": "error", "text": f"Domain configuration failed: {config_result.get('error', 'unknown error')}"}
                except Exception as e:
                    message = {"type": "error", "text": f"Domain configuration failed: {str(e)}"}
            else:
                message = {"type": "error", "text": "Unknown configuration action"}

            config_status = transport_manager.is_configured()
            domain_config = domain_rotation_manager.get_config()
            budget_status = domain_rotation_manager.get_budget_status()
            active_domain = domain_rotation_manager.get_active_domain()
        
        return render_template("email_config.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              message=message,
                              domain_config=domain_config,
                              config_status=config_status,
                              budget_status=budget_status,
                              active_domain=active_domain)

    @email_security_bp.route('/<string:url_addition>/email/send', methods=["POST"])
    def email_send_api(url_addition):
        """API endpoint for sending emails"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"success": False, "error": "No session"})
        
        try:
            data = request.get_json()
            composer = EmailComposer()
            
            result = composer.send_email(
                to_email=data.get("to"),
                subject=data.get("subject"),
                body=data.get("body"),
                from_email=data.get("from")
            )
            
            return jsonify(result)
        except Exception as e:
            logging.exception("Error in email_send_api")
            return jsonify({"success": False, "error": "Failed to send email"})

    @email_security_bp.route('/<string:url_addition>/email/receive', methods=["POST"])
    def email_receive_api(url_addition):
        """API endpoint for receiving emails"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"success": False, "error": "No session"})
        
        try:
            if not transport_manager.is_configured().get("imap"):
                return jsonify({"success": False, "error": "IMAP not configured", "emails": []}), 400

            payload = request.get_json(silent=True) or request.form
            limit = payload.get("limit")
            unread_only = _form_bool(payload.get("unread_only"), default=False)

            parsed_limit = int(limit) if limit not in (None, "") else None
            emails = transport_manager.receive_emails(limit=parsed_limit, unread_only=unread_only)

            # Store received emails
            for email_data in emails:
                try:
                    email_storage.add_email(session["_id"], email_data)
                except Exception:
                    logging.exception("Failed to store received email in session inbox")

            return jsonify({"success": True, "emails": emails, "count": len(emails)})
        except Exception as e:
            logging.exception("Error in email_receive_api")
            return jsonify({"success": False, "error": f"Failed to receive emails: {str(e)}"})

    @email_security_bp.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
    def email_domain_rotate(url_addition):
        """API endpoint for domain rotation"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"success": False, "error": "No session"})
        
        try:
            result = domain_rotation_manager.rotate_domain_with_result()
            status_code = 200 if result.get("success") else 400
            return jsonify(result), status_code
        except Exception as e:
            logging.exception("Error in email_domain_rotate")
            return jsonify({"success": False, "error": "Failed to rotate domain"})

    return email_security_bp