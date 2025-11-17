"""
Tests for email transport module (SMTP/IMAP)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from email_transport import (
    SMTPTransport, IMAPTransport, EmailTransportManager
)


class TestSMTPTransport:
    """Test SMTP email sending"""
    
    @patch('email_transport.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp):
        """Test successful email sending"""
        # Setup mock
        mock_server = Mock()
        mock_smtp.return_value = mock_server
        
        # Create transport
        transport = SMTPTransport(
            "smtp.test.com", 587, "test@test.com", "password", True
        )
        
        # Send email
        result = transport.send_email(
            "from@test.com",
            "to@test.com",
            "Test Subject",
            "Test Body"
        )
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@test.com", "password")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()
    
    @patch('email_transport.smtplib.SMTP')
    def test_send_email_failure(self, mock_smtp):
        """Test email sending failure"""
        # Setup mock to raise exception
        mock_smtp.side_effect = Exception("Connection failed")
        
        # Create transport
        transport = SMTPTransport(
            "smtp.test.com", 587, "test@test.com", "password", True
        )
        
        # Send email
        result = transport.send_email(
            "from@test.com",
            "to@test.com",
            "Test Subject",
            "Test Body"
        )
        
        assert result is False
    
    @patch('email_transport.smtplib.SMTP')
    def test_test_connection_success(self, mock_smtp):
        """Test SMTP connection test success"""
        mock_server = Mock()
        mock_smtp.return_value = mock_server
        
        transport = SMTPTransport(
            "smtp.test.com", 587, "test@test.com", "password", True
        )
        
        result = transport.test_connection()
        assert result is True
        mock_server.login.assert_called_once()
        mock_server.quit.assert_called_once()


class TestIMAPTransport:
    """Test IMAP email receiving"""
    
    def test_extract_plain_text_simple(self):
        """Test plain text extraction from simple email"""
        transport = IMAPTransport("imap.test.com", 993, "test@test.com", "password")
        
        # Create a simple mock email
        mock_msg = Mock()
        mock_msg.is_multipart.return_value = False
        mock_msg.get_content_type.return_value = "text/plain"
        mock_msg.get_payload.return_value = b"Test email body"
        mock_msg.get_content_charset.return_value = "utf-8"
        
        body = transport._extract_plain_text(mock_msg)
        assert "Test email body" in body
    
    def test_extract_plain_text_with_html(self):
        """Test that HTML is extracted as text"""
        transport = IMAPTransport("imap.test.com", 993, "test@test.com", "password")
        
        # Create mock email with HTML
        mock_msg = Mock()
        mock_msg.is_multipart.return_value = False
        mock_msg.get_content_type.return_value = "text/html"
        mock_msg.get_payload.return_value = b"<html><body>Test</body></html>"
        mock_msg.get_content_charset.return_value = "utf-8"
        
        body = transport._extract_plain_text(mock_msg)
        assert "[HTML Content - shown as text]" in body
        assert "<html>" in body
    
    @patch('email_transport.imaplib.IMAP4_SSL')
    def test_test_connection_success(self, mock_imap):
        """Test IMAP connection test success"""
        mock_mail = Mock()
        mock_imap.return_value = mock_mail
        
        transport = IMAPTransport("imap.test.com", 993, "test@test.com", "password")
        
        result = transport.test_connection()
        assert result is True
        mock_mail.login.assert_called_once()
        mock_mail.logout.assert_called_once()


class TestEmailTransportManager:
    """Test transport manager"""
    
    @patch('email_transport.SMTPTransport')
    def test_configure_smtp(self, mock_smtp_class):
        """Test SMTP configuration"""
        mock_transport = Mock()
        mock_transport.test_connection.return_value = True
        mock_smtp_class.return_value = mock_transport
        
        manager = EmailTransportManager()
        result = manager.configure_smtp(
            "smtp.test.com", 587, "test@test.com", "password"
        )
        
        assert result is True
        assert manager.smtp_transport is not None
    
    @patch('email_transport.IMAPTransport')
    def test_configure_imap(self, mock_imap_class):
        """Test IMAP configuration"""
        mock_transport = Mock()
        mock_transport.test_connection.return_value = True
        mock_imap_class.return_value = mock_transport
        
        manager = EmailTransportManager()
        result = manager.configure_imap(
            "imap.test.com", 993, "test@test.com", "password"
        )
        
        assert result is True
        assert manager.imap_transport is not None
    
    def test_is_configured(self):
        """Test configuration status check"""
        manager = EmailTransportManager()
        
        status = manager.is_configured()
        assert status['smtp'] is False
        assert status['imap'] is False
        
        # Mock configure
        manager.smtp_transport = Mock()
        status = manager.is_configured()
        assert status['smtp'] is True
