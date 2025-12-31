# Email System Routes Blueprint
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from email_system import email_storage, burner_manager, EmailComposer, EmailValidator
from email_security_tools import spoofing_tester, phishing_simulator
from email_transport import transport_manager
from domain_manager import domain_rotation_manager, PorkbunAPIClient
import datetime
import json

def create_email_blueprint(id_generator, get_random_color):
    """Create and configure the email routes blueprint"""
    
    email_bp = Blueprint('email', __name__)
    
    @email_bp.route('/<string:url_addition>/email', methods=["GET"])
    def email_inbox(url_addition):
        """Main email inbox page"""
        from flask import current_app as app
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

    @email_bp.route('/<string:url_addition>/email/yesscript', methods=["GET"])
    def email_inbox_script(url_addition):
        """Email inbox with JavaScript enabled"""
        from flask import current_app as app
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

    @email_bp.route('/<string:url_addition>/email/compose', methods=["GET", "POST"])
    def email_compose(url_addition):
        """Compose and send email"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        message = None
        
        if request.method == "POST":
            composer = EmailComposer()
            
            # Get form data
            to_email = request.form.get("to_email", "").strip()
            subject = request.form.get("subject", "").strip()
            body = request.form.get("body", "").strip()
            from_email = request.form.get("from_email", "").strip()
            raw_mode = request.form.get("raw_mode") == "on"
            
            if raw_mode:
                # Raw mode - user provides complete email
                raw_email = request.form.get("raw_email", "").strip()
                if raw_email:
                    try:
                        result = composer.send_raw_email(raw_email)
                        if result["success"]:
                            message = {"type": "success", "text": "Email sent successfully!"}
                        else:
                            message = {"type": "error", "text": f"Failed to send email: {result['error']}"}
                    except Exception as e:
                        message = {"type": "error", "text": f"Error sending email: {str(e)}"}
                else:
                    message = {"type": "error", "text": "Raw email content is required"}
            else:
                # Standard mode
                if to_email and subject and body:
                    try:
                        result = composer.send_email(
                            to_email=to_email,
                            subject=subject,
                            body=body,
                            from_email=from_email if from_email else None
                        )
                        if result["success"]:
                            message = {"type": "success", "text": "Email sent successfully!"}
                        else:
                            message = {"type": "error", "text": f"Failed to send email: {result['error']}"}
                    except Exception as e:
                        message = {"type": "error", "text": f"Error sending email: {str(e)}"}
                else:
                    message = {"type": "error", "text": "To, Subject, and Body are required"}
        
        return render_template("email_compose.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              message=message)
    
    @email_bp.route('/<string:url_addition>/email/view/<string:email_id>', methods=["GET"])
    def email_view(url_addition, email_id):
        """View specific email"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        email = email_storage.get_email(session["_id"], email_id)
        if not email:
            return ('Email not found', 404)
        
        return render_template("email_view.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              email=email)

    @email_bp.route('/<string:url_addition>/email/edit/<string:email_id>', methods=["GET", "POST"])
    def email_edit(url_addition, email_id):
        """Edit email in raw mode"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        email = email_storage.get_email(session["_id"], email_id)
        if not email:
            return ('Email not found', 404)
        
        message = None
        
        if request.method == "POST":
            raw_content = request.form.get("raw_content", "").strip()
            if raw_content:
                email_storage.update_email_raw(session["_id"], email_id, raw_content)
                message = {"type": "success", "text": "Email updated successfully"}
            else:
                message = {"type": "error", "text": "Raw content cannot be empty"}
        
        return render_template("email_edit.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              email=email,
                              message=message)

    @email_bp.route('/<string:url_addition>/email/delete/<string:email_id>', methods=["POST"])
    def email_delete(url_addition, email_id):
        """Delete email"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"success": False, "error": "No session"})
        
        success = email_storage.delete_email(session["_id"], email_id)
        return jsonify({"success": success})

    @email_bp.route('/<string:url_addition>/email/burner', methods=["GET", "POST"])
    def email_burner(url_addition):
        """Burner email management"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        message = None
        
        if request.method == "POST":
            action = request.form.get("action")
            
            if action == "generate":
                try:
                    burner_email = burner_manager.generate_burner_email(session["_id"])
                    message = {
                        "type": "success", 
                        "text": f"Generated burner email: {burner_email['email']}"
                    }
                except Exception as e:
                    message = {"type": "error", "text": f"Error generating burner: {str(e)}"}
        
        # Get active burners
        burners = burner_manager.get_user_burners(session["_id"])
        
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              burners=burners,
                              message=message,
                              script_enabled=False)

    @email_bp.route('/<string:url_addition>/email/burner/yesscript', methods=["GET"])
    def email_burner_script(url_addition):
        """Burner email management with JavaScript"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        burners = burner_manager.get_user_burners(session["_id"])
        
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              burners=burners,
                              message=None,
                              script_enabled=True)

    @email_bp.route('/<string:url_addition>/email/burner/list', methods=["GET"])
    def email_burner_list(url_addition):
        """API endpoint for burner email list"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"burners": []})
        
        burners = burner_manager.get_user_burners(session["_id"])
        return jsonify({"burners": burners})

    @email_bp.route('/<string:url_addition>/email/burner/expire/<string:email>', methods=["POST"])
    def email_burner_expire(url_addition, email):
        """Expire a burner email"""
        from flask import current_app as app
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify({"success": False, "error": "No session"})
        
        try:
            success = burner_manager.expire_burner_email(session["_id"], email)
            return jsonify({"success": success})
        except Exception as e:
            app.logger.exception("Error expiring burner email for user %s and email %s", session.get("_id"), email)
            return jsonify({"success": False, "error": "An internal error occurred while expiring the burner email."})

    return email_bp
