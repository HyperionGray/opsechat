# Email System Routes
def register_email_routes(app, id_generator, get_random_color, email_storage, burner_manager, 
                         EmailComposer, EmailValidator, spoofing_tester, phishing_simulator, 
                         transport_manager, domain_rotation_manager, PorkbunAPIClient):
    """Register email routes with the Flask app"""
    from flask import render_template, jsonify, request, session, redirect
    
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

    @app.route('/<string:url_addition>/email/compose', methods=["GET", "POST"])
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

    @app.route('/<string:url_addition>/email/view/<string:email_id>', methods=["GET"])
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

    @app.route('/<string:url_addition>/email/edit/<string:email_id>', methods=["GET", "POST"])
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
            raw_content = request.form.get("raw_email", "")
            updated_email = EmailComposer.parse_raw_email(raw_content)
            email_storage.update_email(session["_id"], email_id, updated_email)
            return redirect(f"/{app.config['path']}/email/view/{email_id}", code=302)
        
        raw_email = EmailComposer.format_raw_email(email)
        
        return render_template("email_edit.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              email=email,
                              raw_email=raw_email,
                              script_enabled=False)

    @app.route('/<string:url_addition>/email/delete/<string:email_id>', methods=["POST"])
    def email_delete(url_addition, email_id):
        """Delete email"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return ('Unauthorized', 401)
        
        email_storage.delete_email(session["_id"], email_id)
        return redirect(f"/{app.config['path']}/email", code=302)

    @app.route('/<string:url_addition>/email/burner', methods=["GET", "POST"])
    def email_burner(url_addition):
        """Generate burner email address - Modern rotating interface"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        # Cleanup expired burners
        burner_manager.cleanup_expired()
        
        if request.method == "POST":
            action = request.form.get("action", "generate")
            
            if action == "generate":
                burner_email = burner_manager.generate_burner_email(session["_id"])
                email_storage.create_user_inbox(session["_id"])
            elif action == "rotate":
                old_email = request.form.get("old_email")
                burner_email = burner_manager.rotate_burner(session["_id"], old_email)
                email_storage.create_user_inbox(session["_id"])
        
        # Get all active burners for this user
        active_burners = burner_manager.get_user_burners(session["_id"])
        
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              active_burners=active_burners,
                              script_enabled=False)

    @app.route('/<string:url_addition>/email/burner/yesscript', methods=["GET"])
    def email_burner_script(url_addition):
        """Burner email with JavaScript enabled"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            session["_id"] = id_generator()
            session["color"] = get_random_color()
        
        burner_manager.cleanup_expired()
        active_burners = burner_manager.get_user_burners(session["_id"])
        
        return render_template("email_burner.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              active_burners=active_burners,
                              script_enabled=True)

    @app.route('/<string:url_addition>/email/burner/list', methods=["GET"])
    def email_burner_list_json(url_addition):
        """Get active burners as JSON (for AJAX refresh)"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return jsonify([])
        
        burner_manager.cleanup_expired()
        active_burners = burner_manager.get_user_burners(session["_id"])
        
        return jsonify(active_burners)

    @app.route('/<string:url_addition>/email/burner/expire/<string:email>', methods=["POST"])
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

    # Email Security Testing Routes
    @app.route('/<string:url_addition>/email/security/spoof-test', methods=["GET", "POST"])
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

    @app.route('/<string:url_addition>/email/security/phishing-sim', methods=["GET", "POST"])
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

    # Email Configuration Routes
    @app.route('/<string:url_addition>/email/config', methods=["GET", "POST"])
    def email_config(url_addition):
        """Configure SMTP/IMAP settings"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return redirect(f"/{app.config['path']}/email", code=302)
        
        message = None
        config_status = transport_manager.is_configured()
        
        if request.method == "POST":
            action = request.form.get("action")
            
            if action == "configure_smtp":
                smtp_server = request.form.get("smtp_server", "")
                smtp_port = int(request.form.get("smtp_port", "587"))
                smtp_username = request.form.get("smtp_username", "")
                smtp_password = request.form.get("smtp_password", "")
                use_tls = request.form.get("use_tls", "true") == "true"
                
                success = transport_manager.configure_smtp(
                    smtp_server, smtp_port, smtp_username, smtp_password, use_tls
                )
                
                message = {
                    'type': 'success' if success else 'error',
                    'text': 'SMTP configured successfully' if success else 'SMTP configuration failed'
                }
            
            elif action == "configure_imap":
                imap_server = request.form.get("imap_server", "")
                imap_port = int(request.form.get("imap_port", "993"))
                imap_username = request.form.get("imap_username", "")
                imap_password = request.form.get("imap_password", "")
                use_ssl = request.form.get("use_ssl", "true") == "true"
                
                success = transport_manager.configure_imap(
                    imap_server, imap_port, imap_username, imap_password, use_ssl
                )
                
                message = {
                    'type': 'success' if success else 'error',
                    'text': 'IMAP configured successfully' if success else 'IMAP configuration failed'
                }
            
            elif action == "configure_domain_api":
                api_key = request.form.get("api_key", "")
                api_secret = request.form.get("api_secret", "")
                monthly_budget = float(request.form.get("monthly_budget", "50.0"))
                
                if api_key and api_secret:
                    porkbun_client = PorkbunAPIClient(api_key, api_secret)
                    domain_rotation_manager.set_api_client(porkbun_client)
                    domain_rotation_manager.monthly_budget = monthly_budget
                    
                    message = {
                        'type': 'success',
                        'text': 'Domain API configured successfully'
                    }
                else:
                    message = {
                        'type': 'error',
                        'text': 'API key and secret are required'
                    }
            
            config_status = transport_manager.is_configured()
        
        budget_status = domain_rotation_manager.get_budget_status()
        active_domain = domain_rotation_manager.get_active_domain()
        
        return render_template("email_config.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              config_status=config_status,
                              budget_status=budget_status,
                              active_domain=active_domain,
                              message=message,
                              script_enabled=False)

    @app.route('/<string:url_addition>/email/send', methods=["POST"])
    def email_send_real(url_addition):
        """Actually send email via SMTP"""
        if url_addition != app.config["path"]:
            return ('', 404)
        
        if "_id" not in session:
            return ('Unauthorized', 401)
        
        # Get form data
        from_addr = request.form.get("from", "")
        to_addr = request.form.get("to", "")
        subject = request.form.get("subject", "")
        body = request.form.get("body", "")
        
        # Try to send via SMTP
        success = transport_manager.send_email(from_addr, to_addr, subject, body)
        
        if success:
            # Also add to local storage
            email = EmailComposer.create_email(from_addr, to_addr, subject, body)
            email_storage.add_email(session["_id"], email)
        
        return redirect(f"/{app.config['path']}/email", code=302)

    @app.route('/<string:url_addition>/email/receive', methods=["POST"])
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

    @app.route('/<string:url_addition>/email/domain/rotate', methods=["POST"])
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
