"""
Email transport module for SMTP/IMAP integration
Handles real email sending and receiving
"""
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Dict, List, Optional
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class SMTPTransport:
    """
    Handle SMTP email sending
    Supports plain text emails with PGP encryption
    """
    
    def __init__(self, smtp_server: str, smtp_port: int, username: str, 
                 password: str, use_tls: bool = True):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_tls = use_tls
    
    def send_email(self, from_addr: str, to_addr: str, subject: str, 
                   body: str, headers: Optional[Dict] = None) -> bool:
        """
        Send email via SMTP
        Returns True on success, False on failure
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_addr
            msg['To'] = to_addr
            msg['Subject'] = Header(subject, 'utf-8')
            
            # Add custom headers if provided
            if headers:
                for key, value in headers.items():
                    if key.lower() not in ['from', 'to', 'subject']:
                        msg[key] = value
            
            # Add body as plain text
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Connect and send
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_addr}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test SMTP connection"""
        try:
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
            
            server.login(self.username, self.password)
            server.quit()
            return True
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False


class IMAPTransport:
    """
    Handle IMAP email receiving
    Fetches plain text emails only
    """
    
    def __init__(self, imap_server: str, imap_port: int, username: str, 
                 password: str, use_ssl: bool = True):
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
    
    def fetch_emails(self, folder: str = 'INBOX', limit: Optional[int] = None, 
                     unread_only: bool = False) -> List[Dict]:
        """
        Fetch emails from IMAP server
        Returns list of email dictionaries
        """
        emails = []
        
        try:
            # Connect to IMAP server
            if self.use_ssl:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                mail = imaplib.IMAP4(self.imap_server, self.imap_port)
            
            mail.login(self.username, self.password)
            mail.select(folder)
            
            # Search for emails
            search_criteria = 'UNSEEN' if unread_only else 'ALL'
            status, messages = mail.search(None, search_criteria)
            
            if status != 'OK':
                logger.error("Failed to search emails")
                return emails
            
            email_ids = messages[0].split()
            
            # Apply limit
            if limit:
                email_ids = email_ids[-limit:]
            
            # Fetch each email
            for email_id in email_ids:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                if status != 'OK':
                    continue
                
                # Parse email
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Extract email data
                email_dict = self._parse_email_message(email_message)
                if email_dict:
                    emails.append(email_dict)
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
        
        return emails
    
    def _parse_email_message(self, msg: email.message.Message) -> Optional[Dict]:
        """
        Parse email message into dictionary
        Extracts plain text only, converts HTML/images to text
        """
        try:
            # Extract headers
            from_addr = msg.get('From', '')
            to_addr = msg.get('To', '')
            subject = msg.get('Subject', '')
            date_str = msg.get('Date', '')
            
            # Parse date
            timestamp = datetime.now()
            if date_str:
                try:
                    timestamp = email.utils.parsedate_to_datetime(date_str)
                except (ValueError, TypeError, AttributeError):
                    pass
            
            # Extract body (plain text only)
            body = self._extract_plain_text(msg)
            
            # Extract all headers
            headers = {}
            for key, value in msg.items():
                headers[key] = value
            
            return {
                'from': from_addr,
                'to': to_addr,
                'subject': subject,
                'body': body,
                'timestamp': timestamp,
                'headers': headers,
                'is_pgp': "-----BEGIN PGP MESSAGE-----" in body,
            }
            
        except Exception as e:
            logger.error(f"Failed to parse email: {e}")
            return None
    
    def _extract_plain_text(self, msg: email.message.Message) -> str:
        """
        Extract plain text from email
        If HTML, return it as text (not rendered)
        If images, return description as text
        """
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Get plain text parts
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body += payload.decode(charset, errors='ignore')
                    except (AttributeError, UnicodeDecodeError, LookupError):
                        pass
                
                # Convert HTML to text representation
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        html_content = payload.decode(charset, errors='ignore')
                        body += f"\n[HTML Content - shown as text]:\n{html_content}\n"
                    except (AttributeError, UnicodeDecodeError, LookupError):
                        pass
                
                # Note other content types as text
                elif content_type.startswith("image/"):
                    filename = part.get_filename() or "unknown"
                    body += f"\n[Image: {filename} - {content_type}]\n"
                
                elif "attachment" in content_disposition:
                    filename = part.get_filename() or "unknown"
                    body += f"\n[Attachment: {filename} - {content_type}]\n"
        
        else:
            # Not multipart
            content_type = msg.get_content_type()
            
            if content_type == "text/plain":
                try:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='ignore')
                except:
                    body = str(msg.get_payload())
            
            elif content_type == "text/html":
                try:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    html_content = payload.decode(charset, errors='ignore')
                    body = f"[HTML Content - shown as text]:\n{html_content}"
                except:
                    body = "[HTML Content - could not decode]"
        
        return body.strip()
    
    def test_connection(self) -> bool:
        """Test IMAP connection"""
        try:
            if self.use_ssl:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, timeout=10)
            else:
                mail = imaplib.IMAP4(self.imap_server, self.imap_port, timeout=10)
            
            mail.login(self.username, self.password)
            mail.logout()
            return True
        except Exception as e:
            logger.error(f"IMAP connection test failed: {e}")
            return False


class EmailTransportManager:
    """
    Manage SMTP and IMAP transports
    Provides unified interface for sending/receiving emails
    """
    
    def __init__(self):
        self.smtp_transport: Optional[SMTPTransport] = None
        self.imap_transport: Optional[IMAPTransport] = None
    
    def configure_smtp(self, smtp_server: str, smtp_port: int, username: str, 
                      password: str, use_tls: bool = True) -> bool:
        """Configure SMTP transport"""
        try:
            self.smtp_transport = SMTPTransport(
                smtp_server, smtp_port, username, password, use_tls
            )
            return self.smtp_transport.test_connection()
        except Exception as e:
            logger.error(f"Failed to configure SMTP: {e}")
            return False
    
    def configure_imap(self, imap_server: str, imap_port: int, username: str, 
                      password: str, use_ssl: bool = True) -> bool:
        """Configure IMAP transport"""
        try:
            self.imap_transport = IMAPTransport(
                imap_server, imap_port, username, password, use_ssl
            )
            return self.imap_transport.test_connection()
        except Exception as e:
            logger.error(f"Failed to configure IMAP: {e}")
            return False
    
    def send_email(self, from_addr: str, to_addr: str, subject: str, 
                   body: str, headers: Optional[Dict] = None) -> bool:
        """Send email via configured SMTP"""
        if not self.smtp_transport:
            logger.error("SMTP not configured")
            return False
        
        return self.smtp_transport.send_email(
            from_addr, to_addr, subject, body, headers
        )
    
    def receive_emails(self, folder: str = 'INBOX', limit: Optional[int] = None, 
                      unread_only: bool = False) -> List[Dict]:
        """Receive emails via configured IMAP"""
        if not self.imap_transport:
            logger.error("IMAP not configured")
            return []
        
        return self.imap_transport.fetch_emails(folder, limit, unread_only)
    
    def is_configured(self) -> Dict[str, bool]:
        """Check configuration status"""
        return {
            'smtp': self.smtp_transport is not None,
            'imap': self.imap_transport is not None
        }


# Global transport manager
transport_manager = EmailTransportManager()
