# Email Security and Configuration Routes
from flask import Blueprint, render_template, jsonify, request, session
from email_security_tools import spoofing_tester, phishing_simulator
from email_transport import transport_manager
from domain_manager import domain_rotation_manager
from email_system import EmailComposer, email_storage

def create_email_security_blueprint(id_generator, get_random_color):
    """Create and configure the email security routes blueprint"""
    
    email_security_bp = Blueprint('email_security', __name__)

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
        current_config = transport_manager.get_config()
        domain_config = domain_rotation_manager.get_config()
        
        if request.method == "POST":
            config_type = request.form.get("config_type")
            
            if config_type == "smtp":
                smtp_config = {
                    "smtp_server": request.form.get("smtp_server", "").strip(),
                    "smtp_port": int(request.form.get("smtp_port", 587)),
                    "smtp_username": request.form.get("smtp_username", "").strip(),
                    "smtp_password": request.form.get("smtp_password", "").strip(),
                    "use_tls": request.form.get("use_tls") == "on"
                }
                
                try:
                    transport_manager.configure_smtp(**smtp_config)
                    message = {"type": "success", "text": "SMTP configuration saved successfully"}
                except Exception as e:
                    message = {"type": "error", "text": f"SMTP configuration failed: {str(e)}"}
            
            elif config_type == "imap":
                imap_config = {
                    "imap_server": request.form.get("imap_server", "").strip(),
                    "imap_port": int(request.form.get("imap_port", 993)),
                    "imap_username": request.form.get("imap_username", "").strip(),
                    "imap_password": request.form.get("imap_password", "").strip(),
                    "use_ssl": request.form.get("use_ssl") == "on"
                }
                
                try:
                    transport_manager.configure_imap(**imap_config)
                    message = {"type": "success", "text": "IMAP configuration saved successfully"}
                except Exception as e:
                    message = {"type": "error", "text": f"IMAP configuration failed: {str(e)}"}
            
            elif config_type == "domain":
                domain_config_data = {
                    "api_key": request.form.get("porkbun_api_key", "").strip(),
                    "secret_key": request.form.get("porkbun_secret_key", "").strip(),
                    "monthly_budget": float(request.form.get("monthly_budget", 10.0))
                }
                
                try:
                    domain_rotation_manager.configure(**domain_config_data)
                    message = {"type": "success", "text": "Domain configuration saved successfully"}
                except Exception as e:
                    message = {"type": "error", "text": f"Domain configuration failed: {str(e)}"}
        
        return render_template("email_config.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              message=message,
                              current_config=current_config,
                              domain_config=domain_config)

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
            return jsonify({"success": False, "error": str(e)})

    @email_security_bp.route('/<string:url_addition>/email/receive', methods=["POST"])
    def email_receive_api(url_addition):
        """API endpoint for receiving emails"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"success": False, "error": "No session"})
        
        try:
            result = transport_manager.receive_emails()
            
            # Store received emails
            if result["success"] and result["emails"]:
                for email_data in result["emails"]:
                    email_storage.add_email(session["_id"], email_data)
            
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    @email_security_bp.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
    def email_domain_rotate(url_addition):
        """API endpoint for domain rotation"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"success": False, "error": "No session"})
        
        try:
            result = domain_rotation_manager.rotate_domain()
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    return email_security_bp