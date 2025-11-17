"""
Tests for email security tools (spoofing detection and phishing simulation)
"""
import pytest
from email_security_tools import SpoofingTester, PhishingSimulator


class TestSpoofingTester:
    """Test email spoofing detection functionality"""
    
    def test_add_test_domain(self):
        tester = SpoofingTester()
        tester.add_test_domain("example.com")
        assert "example.com" in tester.test_domains
    
    def test_generate_spoof_variants(self):
        tester = SpoofingTester()
        variants = tester.generate_spoof_variants("example.com")
        
        # Should generate multiple variants
        assert len(variants) >= 3
        
        # Check that variants have required fields
        for variant in variants:
            assert 'type' in variant
            assert 'domain' in variant
            assert 'email' in variant
            assert 'risk_level' in variant
    
    def test_test_spoofing_detection_exact_match(self):
        tester = SpoofingTester()
        result = tester.test_spoofing_detection("test@example.com", "example.com")
        
        assert result['email'] == "test@example.com"
        assert result['domain'] == "example.com"
        assert result['legitimate_domain'] == "example.com"
        assert 'risk_score' in result
    
    def test_test_spoofing_detection_subdomain(self):
        tester = SpoofingTester()
        result = tester.test_spoofing_detection("test@fake.example.com", "example.com")
        
        assert result['is_suspicious'] is True
        assert result['risk_score'] > 0
        assert len(result['warnings']) > 0
    
    def test_extract_domain(self):
        tester = SpoofingTester()
        domain = tester._extract_domain("user@example.com")
        assert domain == "example.com"
    
    def test_levenshtein_distance(self):
        tester = SpoofingTester()
        
        # Same strings
        assert tester._levenshtein_distance("test", "test") == 0
        
        # One character difference
        assert tester._levenshtein_distance("test", "tost") == 1
        
        # Multiple differences
        assert tester._levenshtein_distance("test", "best") == 1
    
    def test_contains_unicode_lookalikes(self):
        tester = SpoofingTester()
        
        # ASCII only
        assert tester._contains_unicode_lookalikes("example.com") is False
        
        # Contains Cyrillic 'a'
        assert tester._contains_unicode_lookalikes("exаmple.com") is True


class TestPhishingSimulator:
    """Test phishing simulation functionality"""
    
    def test_enable_persist_mode(self):
        sim = PhishingSimulator()
        sim.enable_persist_mode("user1")
        
        assert "user1" in sim.active_simulations
        assert sim.active_simulations["user1"]["enabled"] is True
    
    def test_disable_persist_mode(self):
        sim = PhishingSimulator()
        sim.enable_persist_mode("user1")
        sim.disable_persist_mode("user1")
        
        assert "user1" not in sim.active_simulations
    
    def test_create_phishing_email_generic(self):
        sim = PhishingSimulator()
        email = sim.create_phishing_email("user1", "generic")
        
        assert email['is_phishing_sim'] is True
        assert email['template'] == 'generic'
        assert 'from' in email
        assert 'to' in email
        assert 'subject' in email
        assert 'body' in email
        assert 'indicators' in email
    
    def test_create_phishing_email_ceo_fraud(self):
        sim = PhishingSimulator()
        email = sim.create_phishing_email("user1", "ceo_fraud")
        
        assert email['template'] == 'ceo_fraud'
        assert 'authority_impersonation' in email['indicators']
    
    def test_create_phishing_email_tech_support(self):
        sim = PhishingSimulator()
        email = sim.create_phishing_email("user1", "tech_support")
        
        assert email['template'] == 'tech_support'
        assert 'typosquat' in email['indicators']
    
    def test_record_user_action_clicked(self):
        sim = PhishingSimulator()
        sim.enable_persist_mode("user1")
        
        result = sim.record_user_action("user1", "email123", "clicked")
        
        assert result['warning'] == '🚨 YOU JUST GOT OWNED! 🚨'
        assert result['score_change'] < 0
        assert sim.active_simulations["user1"]["missed"] == 1
    
    def test_record_user_action_reported(self):
        sim = PhishingSimulator()
        sim.enable_persist_mode("user1")
        
        result = sim.record_user_action("user1", "email123", "reported")
        
        assert result['warning'] == '✅ GOOD CATCH!'
        assert result['score_change'] > 0
        assert sim.active_simulations["user1"]["detected"] == 1
    
    def test_get_user_stats(self):
        sim = PhishingSimulator()
        sim.enable_persist_mode("user1")
        
        stats = sim.get_user_stats("user1")
        
        assert stats['user_id'] == "user1"
        assert 'score' in stats
        assert 'level' in stats
        assert 'simulations' in stats
    
    def test_check_achievements(self):
        sim = PhishingSimulator()
        sim.enable_persist_mode("user1")
        
        # Trigger first detection achievement
        sim.record_user_action("user1", "email1", "reported")
        
        stats = sim.get_user_stats("user1")
        assert 'first_detection' in stats['achievements']
    
    def test_multiple_simulations_tracking(self):
        sim = PhishingSimulator()
        sim.enable_persist_mode("user1")
        
        # Generate multiple emails
        sim.create_phishing_email("user1", "generic")
        sim.create_phishing_email("user1", "ceo_fraud")
        sim.create_phishing_email("user1", "tech_support")
        
        assert sim.active_simulations["user1"]["emails_sent"] == 3
