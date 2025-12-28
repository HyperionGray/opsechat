"""
Email Routes Blueprint for opsechat

This module contains all email-related routes extracted from runserver.py
to improve code organization and maintainability.
"""

from flask import Blueprint, render_template, request, session, redirect, current_app
from email_system import email_storage, burner_manager, EmailComposer, EmailValidator
from email_security_tools import spoofing_tester, phishing_simulator
from email_transport import transport_manager
from domain_manager import domain_rotation_manager
from utils import id_generator, get_random_color


# Create blueprint
email_bp = Blueprint('email', __name__)


@email_bp.route('/<string:url_addition>/email', methods=["GET"])
def email_inbox(url_addition):
    """Email inbox view"""
    if url_addition != current_app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    email_storage.create_user_inbox(session["_id"])
    emails = email_storage.get_emails(session["_id"])
    
    return render_template("email_inbox.html",
                          hostname=current_app.config["hostname"],
                          path=current_app.config["path"],
                          emails=emails,
                          script_enabled=True)


@email_bp.route('/<string:url_addition>/email/compose', methods=["GET", "POST"])
def email_compose(url_addition):
    """Compose and send email"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    if request.method == "POST":
        raw_mode = request.form.get("raw_mode") == "true"
        send_via_smtp = request.form.get("send_via_smtp") == "true"
        
        if raw_mode:
            # Parse raw email
            raw_content = request.form.get("raw_email", "")
            email = EmailComposer.parse_raw_email(raw_content)
        else:
            # Standard compose
            email = EmailComposer.create_email(
                from_addr=request.form.get("from", ""),
                to_addr=request.form.get("to", ""),
                subject=request.form.get("subject", ""),
                body=request.form.get("body", ""),
                headers={}
            )
        
        # Send via SMTP if configured and requested
        if send_via_smtp and transport_manager.is_configured()['smtp']:
            success = transport_manager.send_email(
                email['from'],
                email['to'],
                email['subject'],
                email['body'],
                email.get('headers', {})
            )
            if not success:
                # Could add flash message here
                pass
        
        # Always add to local inbox for reference
        email_storage.add_email(session["_id"], email)
        
        return redirect(f"/{app.config['path']}/email", code=302)
    
    # Check if SMTP is configured for the form
    smtp_configured = transport_manager.is_configured()['smtp']
    
    return render_template("email_compose.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          smtp_configured=smtp_configured,
                          script_enabled=False)


@email_bp.route('/<string:url_addition>/email/view/<string:email_id>', methods=["GET"])
def email_view(url_addition, email_id):
    """View specific email"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    email = email_storage.get_email(session["_id"], email_id)
    if not email:
        return ('Email not found', 404)
    
    return render_template("email_view.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          email=email,
                          script_enabled=False)


@email_bp.route('/<string:url_addition>/email/edit/<string:email_id>', methods=["GET", "POST"])
def email_edit(url_addition, email_id):
    """Edit email in raw mode"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    email = email_storage.get_email(session["_id"], email_id)
    if not email:
        return ('Email not found', 404)
    
    if request.method == "POST":
        # Update email with raw content
        raw_content = request.form.get("raw_email", "")
        updated_email = EmailComposer.parse_raw_email(raw_content)
        updated_email['id'] = email_id  # Preserve ID
        email_storage.update_email(session["_id"], email_id, updated_email)
        return redirect(f"/{app.config['path']}/email/view/{email_id}", code=302)
    
    # Convert email back to raw format for editing
    raw_email = EmailComposer.email_to_raw(email)
    
    return render_template("email_edit.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          email=email,
                          raw_email=raw_email,
                          script_enabled=False)


@email_bp.route('/<string:url_addition>/email/config', methods=["GET", "POST"])
def email_config(url_addition):
    """Email configuration"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return redirect(f"/{app.config['path']}/email", code=302)
    
    if request.method == "POST":
        # Update SMTP configuration
        smtp_config = {
            'host': request.form.get('smtp_host', ''),
            'port': int(request.form.get('smtp_port', '587')),
            'username': request.form.get('smtp_username', ''),
            'password': request.form.get('smtp_password', ''),
            'use_tls': request.form.get('smtp_tls') == 'true'
        }
        
        # Update IMAP configuration
        imap_config = {
            'host': request.form.get('imap_host', ''),
            'port': int(request.form.get('imap_port', '993')),
            'username': request.form.get('imap_username', ''),
            'password': request.form.get('imap_password', ''),
            'use_ssl': request.form.get('imap_ssl') == 'true'
        }
        
        # Update Porkbun API configuration
        porkbun_config = {
            'api_key': request.form.get('porkbun_api_key', ''),
            'secret_key': request.form.get('porkbun_secret_key', ''),
            'monthly_budget': float(request.form.get('monthly_budget', '10.0'))
        }
        
        # Configure transport manager
        transport_manager.configure_smtp(**smtp_config)
        transport_manager.configure_imap(**imap_config)
        
        # Configure domain rotation manager
        domain_rotation_manager.configure_porkbun(**porkbun_config)
        
        return redirect(f"/{app.config['path']}/email/config", code=302)
    
    # Get current configuration status
    config_status = transport_manager.is_configured()
    domain_status = domain_rotation_manager.get_status()
    
    return render_template("email_config.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          config_status=config_status,
                          domain_status=domain_status,
                          script_enabled=False)


@email_bp.route('/<string:url_addition>/email/send', methods=["POST"])
def email_send_real(url_addition):
    """Send email via SMTP"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    from_addr = request.form.get("from", "")
    to_addr = request.form.get("to", "")
    subject = request.form.get("subject", "")
    body = request.form.get("body", "")
    
    # Send via SMTP
    success = transport_manager.send_email(from_addr, to_addr, subject, body)
    
    if success:
        # Also add to local storage
        email = EmailComposer.create_email(from_addr, to_addr, subject, body)
        email_storage.add_email(session["_id"], email)
    
    return redirect(f"/{app.config['path']}/email", code=302)


@email_bp.route('/<string:url_addition>/email/receive', methods=["POST"])
def email_receive_real(url_addition):
    """Fetch emails from IMAP"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    # Fetch from IMAP
    limit = int(request.form.get("limit", "10"))
    unread_only = request.form.get("unread_only", "false") == "true"
    
    emails = transport_manager.receive_emails(limit=limit, unread_only=unread_only)
    
    # Add to local storage
    for email in emails:
        email_storage.add_email(session["_id"], email)
    
    return redirect(f"/{app.config['path']}/email", code=302)


@email_bp.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
def email_domain_rotate(url_addition):
    """Rotate to a new domain"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return ('Unauthorized', 401)
    
    # Attempt domain rotation
    new_domain = domain_rotation_manager.rotate_domain()
    
    if new_domain:
        # Update burner manager to use new domain
        burner_manager.set_custom_domain(new_domain)
    
    return redirect(f"/{app.config['path']}/email/config", code=302)