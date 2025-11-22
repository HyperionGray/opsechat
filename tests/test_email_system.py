"""
Tests for the email system module
"""
import datetime
import pytest
from email_system import (
    EmailStorage, EmailValidator, EmailComposer, BurnerEmailManager
)


class TestEmailStorage:
    """Test email storage functionality"""
    
    def test_create_user_inbox(self):
        storage = EmailStorage()
        storage.create_user_inbox("user1")
        assert "user1" in storage.emails
        assert storage.emails["user1"] == []
    
    def test_add_email(self):
        storage = EmailStorage()
        email = {
            'from': 'sender@test.com',
            'to': 'user@test.com',
            'subject': 'Test',
            'body': 'Test body'
        }
        storage.add_email("user1", email)
        
        assert len(storage.emails["user1"]) == 1
        assert storage.emails["user1"][0]['from'] == 'sender@test.com'
        assert 'id' in storage.emails["user1"][0]
        assert 'timestamp' in storage.emails["user1"][0]
    
    def test_get_emails(self):
        storage = EmailStorage()
        email1 = {'from': 'test1@test.com', 'to': 'user@test.com', 'subject': 'Test 1', 'body': 'Body 1'}
        email2 = {'from': 'test2@test.com', 'to': 'user@test.com', 'subject': 'Test 2', 'body': 'Body 2'}
        
        storage.add_email("user1", email1)
        storage.add_email("user1", email2)
        
        emails = storage.get_emails("user1")
        assert len(emails) == 2
        
        limited = storage.get_emails("user1", limit=1)
        assert len(limited) == 1
    
    def test_get_email_by_id(self):
        storage = EmailStorage()
        email = {'from': 'test@test.com', 'to': 'user@test.com', 'subject': 'Test', 'body': 'Body'}
        storage.add_email("user1", email)
        
        email_id = storage.emails["user1"][0]['id']
        retrieved = storage.get_email("user1", email_id)
        
        assert retrieved is not None
        assert retrieved['from'] == 'test@test.com'
        assert retrieved['id'] == email_id
    
    def test_delete_email(self):
        storage = EmailStorage()
        email = {'from': 'test@test.com', 'to': 'user@test.com', 'subject': 'Test', 'body': 'Body'}
        storage.add_email("user1", email)
        
        email_id = storage.emails["user1"][0]['id']
        result = storage.delete_email("user1", email_id)
        
        assert result is True
        assert len(storage.emails["user1"]) == 0
    
    def test_update_email(self):
        storage = EmailStorage()
        email = {'from': 'test@test.com', 'to': 'user@test.com', 'subject': 'Original', 'body': 'Body'}
        storage.add_email("user1", email)
        
        email_id = storage.emails["user1"][0]['id']
        updated = {'from': 'test@test.com', 'to': 'user@test.com', 'subject': 'Updated', 'body': 'New body'}
        
        result = storage.update_email("user1", email_id, updated)
        assert result is True
        
        retrieved = storage.get_email("user1", email_id)
        assert retrieved['subject'] == 'Updated'
        assert retrieved['body'] == 'New body'


class TestEmailValidator:
    """Test email validation functionality"""
    
    def test_validate_email_address_valid(self):
        assert EmailValidator.validate_email_address("test@example.com") is True
        assert EmailValidator.validate_email_address("user.name+tag@example.co.uk") is True
    
    def test_validate_email_address_invalid(self):
        assert EmailValidator.validate_email_address("invalid") is False
        assert EmailValidator.validate_email_address("@example.com") is False
        assert EmailValidator.validate_email_address("test@") is False
    
    def test_is_pgp_message(self):
        pgp_content = "-----BEGIN PGP MESSAGE-----\nabc\n-----END PGP MESSAGE-----"
        assert EmailValidator.is_pgp_message(pgp_content) is True
        
        plain_content = "This is a plain text message"
        assert EmailValidator.is_pgp_message(plain_content) is False
    
    def test_sanitize_header(self):
        # Test newline removal
        dirty = "Header\nInjection"
        clean = EmailValidator.sanitize_header(dirty)
        assert "\n" not in clean
        assert "\r" not in clean


class TestEmailComposer:
    """Test email composition functionality"""
    
    def test_create_email(self):
        email = EmailComposer.create_email(
            from_addr="sender@test.com",
            to_addr="recipient@test.com",
            subject="Test Subject",
            body="Test body"
        )
        
        assert email['from'] == "sender@test.com"
        assert email['to'] == "recipient@test.com"
        assert email['subject'] == "Test Subject"
        assert email['body'] == "Test body"
        assert email['raw_mode'] is False
        assert email['is_pgp'] is False
    
    def test_create_email_with_pgp(self):
        pgp_body = "-----BEGIN PGP MESSAGE-----\nencrypted\n-----END PGP MESSAGE-----"
        email = EmailComposer.create_email(
            from_addr="sender@test.com",
            to_addr="recipient@test.com",
            subject="Encrypted",
            body=pgp_body
        )
        
        assert email['is_pgp'] is True
    
    def test_parse_raw_email(self):
        raw = """From: sender@test.com
To: recipient@test.com
Subject: Test Subject
X-Custom-Header: Custom Value

This is the email body."""
        
        email = EmailComposer.parse_raw_email(raw)
        
        assert email['from'] == "sender@test.com"
        assert email['to'] == "recipient@test.com"
        assert email['subject'] == "Test Subject"
        assert email['body'] == "This is the email body."
        assert email['headers']['X-Custom-Header'] == "Custom Value"
        assert email['raw_mode'] is True
    
    def test_format_raw_email(self):
        email = {
            'from': 'sender@test.com',
            'to': 'recipient@test.com',
            'subject': 'Test',
            'body': 'Body text',
            'headers': {'X-Custom': 'Value'}
        }
        
        raw = EmailComposer.format_raw_email(email)
        
        assert "From: sender@test.com" in raw
        assert "To: recipient@test.com" in raw
        assert "Subject: Test" in raw
        assert "X-Custom: Value" in raw
        assert "Body text" in raw


class TestBurnerEmailManager:
    """Test burner email management"""
    
    def test_generate_burner_email(self):
        manager = BurnerEmailManager()
        email = manager.generate_burner_email("user1", "test.onion")
        
        assert "@test.onion" in email
        assert email in manager.burner_addresses
        assert manager.burner_addresses[email]['user_id'] == "user1"
    
    def test_get_user_for_burner(self):
        manager = BurnerEmailManager()
        email = manager.generate_burner_email("user1")
        
        user_id = manager.get_user_for_burner(email)
        assert user_id == "user1"
    
    def test_get_user_for_nonexistent_burner(self):
        manager = BurnerEmailManager()
        user_id = manager.get_user_for_burner("nonexistent@test.com")
        assert user_id is None
    
    def test_cleanup_expired(self):
        manager = BurnerEmailManager()
        email = manager.generate_burner_email("user1")
        
        # Manually expire the burner
        manager.burner_addresses[email]['expires_at'] = datetime.datetime.now() - datetime.timedelta(hours=1)
        
        manager.cleanup_expired()
        assert email not in manager.burner_addresses
    
    def test_get_user_burners(self):
        """Test retrieving all active burners for a user"""
        manager = BurnerEmailManager()
        email1 = manager.generate_burner_email("user1")
        email2 = manager.generate_burner_email("user1")
        email3 = manager.generate_burner_email("user2")
        
        burners = manager.get_user_burners("user1")
        assert len(burners) == 2
        assert any(b['email'] == email1 for b in burners)
        assert any(b['email'] == email2 for b in burners)
        assert not any(b['email'] == email3 for b in burners)
    
    def test_rotate_burner(self):
        """Test rotating to a new burner email"""
        manager = BurnerEmailManager()
        old_email = manager.generate_burner_email("user1")
        
        new_email = manager.rotate_burner("user1", old_email)
        
        assert new_email != old_email
        assert old_email not in manager.burner_addresses
        assert new_email in manager.burner_addresses
    
    def test_expire_burner(self):
        """Test manually expiring a burner"""
        manager = BurnerEmailManager()
        email = manager.generate_burner_email("user1")
        
        result = manager.expire_burner(email)
        
        assert result is True
        assert email not in manager.burner_addresses
    
    def test_custom_domain(self):
        """Test setting custom domain for burners"""
        manager = BurnerEmailManager()
        manager.set_custom_domain("custom.xyz")
        
        email = manager.generate_burner_email("user1")
        
        assert "@custom.xyz" in email
    
    def test_custom_hours_valid(self):
        """Test generating burner with custom validity period"""
        manager = BurnerEmailManager()
        email = manager.generate_burner_email("user1", hours_valid=48)
        
        info = manager.burner_addresses[email]
        time_diff = info['expires_at'] - info['created_at']
        
        # Should be approximately 48 hours (allowing for small time differences)
        assert 47.9 < time_diff.total_seconds() / 3600 < 48.1
    
    def test_user_burners_excludes_expired(self):
        """Test that get_user_burners excludes expired burners"""
        manager = BurnerEmailManager()
        active_email = manager.generate_burner_email("user1")
        expired_email = manager.generate_burner_email("user1")
        
        # Manually expire one burner
        manager.burner_addresses[expired_email]['expires_at'] = datetime.datetime.now() - datetime.timedelta(hours=1)
        
        burners = manager.get_user_burners("user1")
        
        assert len(burners) == 1
        assert burners[0]['email'] == active_email
