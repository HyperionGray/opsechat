"""
Security Routes Blueprint for opsechat

This module contains all security testing-related routes extracted from runserver.py
to improve code organization and maintainability.
"""

from flask import Blueprint, render_template, request, session, redirect, app
from email_security_tools import spoofing_tester, phishing_simulator
from email_system import email_storage

# Create blueprint
security_bp = Blueprint('security', __name__)

def get_random_color():
    """Get a random color for user identification"""
    import random
    colors = ["red", "blue", "green", "orange", "purple", "brown", "pink", "gray", "olive", "cyan"]
    return random.choice(colors)

def id_generator(size=6, chars=None):
    """Generate random IDs for ephemeral use"""
    import string
    import random
    if chars is None:
        chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
    return ''.join(random.choice(chars) for _ in range(size))


@security_bp.route('/<string:url_addition>/email/security/spoof-test', methods=["GET", "POST"])
def email_spoof_test(url_addition):
    """Test email spoofing detection"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    results = None
    variants = None
    
    if request.method == "POST":
        test_type = request.form.get("test_type", "detect")
        
        if test_type == "detect":
            # Test spoofing detection
            test_email = request.form.get("test_email", "")
            legitimate_domain = request.form.get("legitimate_domain", "")
            
            if test_email and legitimate_domain:
                results = spoofing_tester.test_spoofing_detection(test_email, legitimate_domain)
        
        elif test_type == "generate":
            # Generate spoofing variants
            target_domain = request.form.get("target_domain", "")
            
            if target_domain:
                variants = spoofing_tester.generate_spoof_variants(target_domain)
    
    return render_template("email_spoof_test.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          results=results,
                          variants=variants,
                          script_enabled=False)


@security_bp.route('/<string:url_addition>/email/security/phishing-sim', methods=["GET", "POST"])
def email_phishing_sim(url_addition):
    """Phishing simulation and training"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    user_id = session["_id"]
    action_result = None
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "enable":
            phishing_simulator.enable_persist_mode(user_id)
            
        elif action == "disable":
            phishing_simulator.disable_persist_mode(user_id)
            
        elif action == "generate":
            template = request.form.get("template", "generic")
            phishing_email = phishing_simulator.create_phishing_email(user_id, template)
            # Add to inbox
            email_storage.add_email(user_id, phishing_email)
            action_result = {
                'type': 'generated',
                'message': 'Phishing simulation email added to your inbox'
            }
    
    # Get user stats
    stats = phishing_simulator.get_user_stats(user_id)
    
    return render_template("email_phishing_sim.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          stats=stats,
                          action_result=action_result,
                          script_enabled=False)