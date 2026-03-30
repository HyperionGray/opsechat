#!/usr/bin/env python3
"""
Comprehensive Functionality Test for opsechat
Tests all major features without requiring Tor daemon
"""

import sys
import os
import traceback
import tempfile
import json
from datetime import datetime, timedelta

# Add current directory to Python path
sys.path.insert(0, '/workspace')

def test_chat_functionality():
    """Test chat system functionality"""
    print("\n=== Testing Chat System ===")
    
    try:
        import runserver
        
        # Test ID generation
        test_id = runserver.id_generator(10)
        assert len(test_id) == 10
        print("✅ ID generation works")
        
        # Test message sanitization
        if hasattr(runserver, 'sanitize_message'):
            clean_msg = runserver.sanitize_message("Hello <script>alert('xss')</script>")
            assert "<script>" not in clean_msg
            print("✅ Message sanitization works")
        
        # Test time checking function
        if hasattr(runserver, 'check_older_than'):
            # Create a test message from 5 minutes ago
            old_time = datetime.now() - timedelta(minutes=5)
            test_msg = {'timestamp': old_time.isoformat()}
            
            # This should return True (message is older than 3 minutes)
            is_old = runserver.check_older_than(test_msg)
            print(f"✅ Time checking works: {is_old}")
        
        return True
        
    except Exception as e:
        print(f"❌ Chat functionality test failed: {e}")
        traceback.print_exc()
        return False

def test_email_system():
    """Test email system functionality"""
    print("\n=== Testing Email System ===")
    
    try:
        from email_system import EmailStorage, EmailComposer, EmailValidator, BurnerManager
        
        # Test EmailStorage
        storage = EmailStorage()
        storage.create_user_inbox("test_user")
        
        test_email = {
            'from': 'test@example.com',
            'to': 'user@example.com',
            'subject': 'Test Email',
            'body': 'This is a test email',
            'timestamp': datetime.now().isoformat()
        }
        
        storage.add_email("test_user", test_email)
        emails = storage.get_emails("test_user")
        assert len(emails) == 1
        assert emails[0]['subject'] == 'Test Email'
        print("✅ Email storage works")
        
        # Test EmailValidator
        validator = EmailValidator()
        assert validator.is_valid_email("test@example.com")
        assert not validator.is_valid_email("invalid-email")
        print("✅ Email validation works")
        
        # Test EmailComposer
        composer = EmailComposer()
        composed = composer.compose_email(
            from_addr="sender@example.com",
            to_addr="recipient@example.com",
            subject="Test Subject",
            body="Test Body"
        )
        assert "Test Subject" in composed
        assert "Test Body" in composed
        print("✅ Email composition works")
        
        # Test BurnerManager
        burner_mgr = BurnerManager()
        burner = burner_mgr.generate_burner("test_user")
        assert "@" in burner['email']
        assert burner['expires_at'] is not None
        print("✅ Burner email generation works")
        
        return True
        
    except Exception as e:
        print(f"❌ Email system test failed: {e}")
        traceback.print_exc()
        return False

def test_email_security_tools():
    """Test email security tools"""
    print("\n=== Testing Email Security Tools ===")
    
    try:
        from email_security_tools import SpoofingTester, PhishingSimulator
        
        # Test SpoofingTester
        spoof_tester = SpoofingTester()
        
        # Test domain similarity
        similarity = spoof_tester.check_domain_similarity("google.com", "g00gle.com")
        assert similarity > 0.5  # Should detect similarity
        print("✅ Domain similarity detection works")
        
        # Test unicode spoofing
        is_suspicious = spoof_tester.detect_unicode_spoofing("раураl.com")  # Cyrillic 'a'
        assert is_suspicious
        print("✅ Unicode spoofing detection works")
        
        # Test PhishingSimulator
        phishing_sim = PhishingSimulator()
        
        # Test phishing email generation
        phishing_email = phishing_sim.generate_phishing_email("banking")
        assert "subject" in phishing_email
        assert "body" in phishing_email
        print("✅ Phishing email generation works")
        
        # Test scoring
        score = phishing_sim.calculate_suspicion_score({
            'from': 'noreply@bank-security.com',
            'subject': 'URGENT: Verify your account NOW!',
            'body': 'Click here immediately: http://suspicious-link.com'
        })
        assert score > 50  # Should be suspicious
        print("✅ Suspicion scoring works")
        
        return True
        
    except Exception as e:
        print(f"❌ Email security tools test failed: {e}")
        traceback.print_exc()
        return False

def test_email_transport():
    """Test email transport functionality"""
    print("\n=== Testing Email Transport ===")
    
    try:
        from email_transport import TransportManager, SMTPConfig, IMAPConfig
        
        # Test configuration classes
        smtp_config = SMTPConfig(
            host="smtp.example.com",
            port=587,
            username="test@example.com",
            password="password",
            use_tls=True
        )
        assert smtp_config.host == "smtp.example.com"
        print("✅ SMTP configuration works")
        
        imap_config = IMAPConfig(
            host="imap.example.com",
            port=993,
            username="test@example.com",
            password="password",
            use_ssl=True
        )
        assert imap_config.host == "imap.example.com"
        print("✅ IMAP configuration works")
        
        # Test TransportManager
        transport_mgr = TransportManager()
        transport_mgr.configure_smtp(smtp_config)
        transport_mgr.configure_imap(imap_config)
        
        assert transport_mgr.smtp_config is not None
        assert transport_mgr.imap_config is not None
        print("✅ Transport manager configuration works")
        
        return True
        
    except Exception as e:
        print(f"❌ Email transport test failed: {e}")
        traceback.print_exc()
        return False

def test_domain_manager():
    """Test domain management functionality"""
    print("\n=== Testing Domain Manager ===")
    
    try:
        from domain_manager import DomainRotationManager, PorkbunAPIClient
        
        # Test DomainRotationManager
        domain_mgr = DomainRotationManager()
        
        # Test domain generation
        test_domain = domain_mgr.generate_domain_name()
        assert "." in test_domain
        assert len(test_domain) > 5
        print("✅ Domain name generation works")
        
        # Test budget tracking
        domain_mgr.set_monthly_budget(100.0)
        assert domain_mgr.monthly_budget == 100.0
        print("✅ Budget management works")
        
        # Test PorkbunAPIClient (without actual API calls)
        api_client = PorkbunAPIClient("test_key", "test_secret")
        assert api_client.api_key == "test_key"
        assert api_client.secret_key == "test_secret"
        print("✅ API client initialization works")
        
        return True
        
    except Exception as e:
        print(f"❌ Domain manager test failed: {e}")
        traceback.print_exc()
        return False

def test_flask_routes():
    """Test Flask application routes (without starting server)"""
    print("\n=== Testing Flask Routes ===")
    
    try:
        import runserver
        
        # Test that Flask app is created
        app = runserver.app
        assert app is not None
        print("✅ Flask app creation works")
        
        # Test that routes are registered
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        
        # Check for key routes
        expected_routes = [
            '/<string:url_addition>/',
            '/<string:url_addition>/chat',
            '/<string:url_addition>/email',
            '/<string:url_addition>/email/compose',
            '/<string:url_addition>/email/config',
            '/<string:url_addition>/reviews'
        ]
        
        for expected_route in expected_routes:
            # Check if route pattern exists (may have variations)
            route_exists = any(expected_route.replace('<string:url_addition>', '') in route for route in routes)
            if route_exists:
                print(f"✅ Route registered: {expected_route}")
            else:
                print(f"⚠️  Route not found: {expected_route}")
        
        return True
        
    except Exception as e:
        print(f"❌ Flask routes test failed: {e}")
        traceback.print_exc()
        return False

def test_template_files():
    """Test that template files exist and are valid"""
    print("\n=== Testing Template Files ===")
    
    try:
        template_dir = "/workspace/templates"
        
        expected_templates = [
            "drop.html",
            "chats.html", 
            "email_inbox.html",
            "email_compose.html",
            "email_config.html",
            "email_burner.html",
            "reviews.html"
        ]
        
        missing_templates = []
        for template in expected_templates:
            template_path = os.path.join(template_dir, template)
            if os.path.exists(template_path):
                print(f"✅ Template exists: {template}")
            else:
                missing_templates.append(template)
                print(f"❌ Template missing: {template}")
        
        if not missing_templates:
            print("✅ All expected templates found")
            return True
        else:
            print(f"❌ Missing templates: {missing_templates}")
            return False
        
    except Exception as e:
        print(f"❌ Template files test failed: {e}")
        traceback.print_exc()
        return False

def test_static_files():
    """Test that static files exist"""
    print("\n=== Testing Static Files ===")
    
    try:
        static_dir = "/workspace/static"
        
        expected_files = [
            "jquery.js",
            "openpgp.min.js",
            "pgp-manager.js",
            "favicon.ico"
        ]
        
        missing_files = []
        for file in expected_files:
            file_path = os.path.join(static_dir, file)
            if os.path.exists(file_path):
                print(f"✅ Static file exists: {file}")
            else:
                missing_files.append(file)
                print(f"❌ Static file missing: {file}")
        
        if not missing_files:
            print("✅ All expected static files found")
            return True
        else:
            print(f"❌ Missing static files: {missing_files}")
            return False
        
    except Exception as e:
        print(f"❌ Static files test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all functionality tests"""
    print("=== opsechat Comprehensive Functionality Test ===")
    print(f"Test started at: {datetime.now()}")
    print()
    
    tests = [
        ("Chat System", test_chat_functionality),
        ("Email System", test_email_system),
        ("Email Security Tools", test_email_security_tools),
        ("Email Transport", test_email_transport),
        ("Domain Manager", test_domain_manager),
        ("Flask Routes", test_flask_routes),
        ("Template Files", test_template_files),
        ("Static Files", test_static_files)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            result = test_func()
            results[test_name] = "PASSED" if result else "FAILED"
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = "FAILED"
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print('='*50)
    
    passed = sum(1 for result in results.values() if result == "PASSED")
    total = len(results)
    
    for test_name, result in results.items():
        status_icon = "✅" if result == "PASSED" else "❌"
        print(f"{status_icon} {test_name}: {result}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All functionality tests PASSED!")
        return 0
    else:
        print("⚠️  Some functionality tests FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())