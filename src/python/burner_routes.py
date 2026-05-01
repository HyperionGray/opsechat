"""
Burner Email Routes Blueprint for opsechat

This module contains all burner email-related routes extracted from runserver.py
to improve code organization and maintainability.
"""

from flask import Blueprint, render_template, request, session, redirect, jsonify, app
from email_system import burner_manager

# Create blueprint
burner_bp = Blueprint('burner', __name__)

def id_generator(size=6, chars=None):
    """Generate random IDs for ephemeral use"""
    import string
    import random
    if chars is None:
        chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
    return ''.join(random.choice(chars) for _ in range(size))


@burner_bp.route('/<string:url_addition>/email/burner', methods=["GET", "POST"])
def email_burner(url_addition):
    """Generate burner email address - Modern rotating interface"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
    
    # Cleanup expired burners
    burner_manager.cleanup_expired()
    
    if request.method == "POST":
        action = request.form.get("action")
        if action == "generate":
            # Generate new burner
            burner_email = burner_manager.generate_burner_email(session["_id"])
        elif action == "rotate":
            # Rotate existing burner
            old_email = request.form.get("old_email")
            burner_email = burner_manager.rotate_burner(session["_id"], old_email)
    
    # Get all active burners for this user
    active_burners = burner_manager.get_user_burners(session["_id"])
    
    return render_template("email_burner.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          active_burners=active_burners,
                          script_enabled=False)


@burner_bp.route('/<string:url_addition>/email/burner/yesscript', methods=["GET"])
def email_burner_script(url_addition):
    """Burner email with JavaScript enabled"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
    
    # Cleanup expired burners
    burner_manager.cleanup_expired()
    active_burners = burner_manager.get_user_burners(session["_id"])
    
    return render_template("email_burner.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          active_burners=active_burners,
                          script_enabled=True)


@burner_bp.route('/<string:url_addition>/email/burner/list', methods=["GET"])
def email_burner_list_json(url_addition):
    """Get active burners as JSON (for AJAX refresh)"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return jsonify([])
    
    burner_manager.cleanup_expired()
    active_burners = burner_manager.get_user_burners(session["_id"])
    
    return jsonify(active_burners)


@burner_bp.route('/<string:url_addition>/email/burner/expire/<string:email>', methods=["POST"])
def email_burner_expire(url_addition, email):
    """Expire a specific burner email"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    # Verify this burner belongs to the user
    burner_user = burner_manager.get_user_for_burner(email)
    if burner_user == session["_id"]:
        burner_manager.expire_burner(email)
    
    return redirect(f"/{app.config['path']}/email/burner", code=302)