"""
Email system module for opsechat
Provides encrypted email inbox functionality with PGP support
"""
import datetime
import string
import random
import re
from hashlib import sha256
from typing import Dict, List, Optional


class EmailStorage:
    """
    In-memory email storage with optional encryption
    Nothing touches disk unless encrypted
    """
    
    def __init__(self):
        self.emails: Dict[str, List[Dict]] = {}  # user_id -> list of emails
        self.user_keys: Dict[str, Dict] = {}  # user_id -> {master_key, email_key}
        
    def create_user_inbox(self, user_id: str) -> None:
        """Initialize inbox for a user"""
        if user_id not in self.emails:
            self.emails[user_id] = []
            
    def add_email(self, user_id: str, email: Dict) -> None:
        """Add email to user's inbox"""
        if user_id not in self.emails:
            self.create_user_inbox(user_id)
        
        email['timestamp'] = datetime.datetime.now()
        email['id'] = self._generate_email_id()
        self.emails[user_id].append(email)
        
    def get_emails(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve user's emails"""
        if user_id not in self.emails:
            return []
        
        emails = self.emails[user_id]
        if limit:
            return emails[-limit:]
        return emails
    
    def get_email(self, user_id: str, email_id: str) -> Optional[Dict]:
        """Get specific email by ID"""
        if user_id not in self.emails:
            return None
            
        for email in self.emails[user_id]:
            if email.get('id') == email_id:
                return email
        return None
    
    def delete_email(self, user_id: str, email_id: str) -> bool:
        """Delete specific email"""
        if user_id not in self.emails:
            return False
            
        for i, email in enumerate(self.emails[user_id]):
            if email.get('id') == email_id:
                self.emails[user_id].pop(i)
                return True
        return False
    
    def update_email(self, user_id: str, email_id: str, updated_email: Dict) -> bool:
        """Update email (for raw mode editing)"""
        if user_id not in self.emails:
            return False
            
        for i, email in enumerate(self.emails[user_id]):
            if email.get('id') == email_id:
                updated_email['id'] = email_id
                updated_email['timestamp'] = email.get('timestamp', datetime.datetime.now())
                self.emails[user_id][i] = updated_email
                return True
        return False
    
    def _generate_email_id(self) -> str:
        """Generate unique email ID"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(16))


class EmailValidator:
    """Validate and sanitize email data"""
    
    @staticmethod
    def validate_email_address(email: str) -> bool:
        """Basic email validation"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_pgp_message(content: str) -> bool:
        """Check if content is PGP encrypted"""
        return "-----BEGIN PGP MESSAGE-----" in content
    
    @staticmethod
    def sanitize_header(header_value: str) -> str:
        """Sanitize email header value"""
        # Remove newlines to prevent header injection
        return header_value.replace('\n', '').replace('\r', '')


class EmailComposer:
    """Compose and format emails"""
    
    @staticmethod
    def create_email(from_addr: str, to_addr: str, subject: str, 
                     body: str, headers: Optional[Dict] = None) -> Dict:
        """Create email dictionary"""
        email = {
            'from': from_addr,
            'to': to_addr,
            'subject': subject,
            'body': body,
            'headers': headers or {},
            'raw_mode': False,
            'is_pgp': EmailValidator.is_pgp_message(body),
        }
        return email
    
    @staticmethod
    def parse_raw_email(raw_content: str) -> Dict:
        """Parse raw email content (headers + body)"""
        parts = raw_content.split('\n\n', 1)
        
        headers = {}
        body = ''
        
        if len(parts) > 0:
            # Parse headers
            header_lines = parts[0].split('\n')
            for line in header_lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
        
        if len(parts) > 1:
            body = parts[1]
        
        return {
            'from': headers.get('From', ''),
            'to': headers.get('To', ''),
            'subject': headers.get('Subject', ''),
            'body': body,
            'headers': headers,
            'raw_mode': True,
            'is_pgp': EmailValidator.is_pgp_message(body),
        }
    
    @staticmethod
    def format_raw_email(email: Dict) -> str:
        """Format email as raw text (headers + body)"""
        lines = []
        
        # Standard headers
        if email.get('from'):
            lines.append(f"From: {email['from']}")
        if email.get('to'):
            lines.append(f"To: {email['to']}")
        if email.get('subject'):
            lines.append(f"Subject: {email['subject']}")
        
        # Additional headers
        for key, value in email.get('headers', {}).items():
            if key.lower() not in ['from', 'to', 'subject']:
                lines.append(f"{key}: {value}")
        
        # Separator
        lines.append('')
        
        # Body
        lines.append(email.get('body', ''))
        
        return '\n'.join(lines)


class BurnerEmailManager:
    """Manage temporary burner email addresses"""
    
    def __init__(self):
        self.burner_addresses: Dict[str, Dict] = {}  # email -> {user_id, expires_at}
        self.custom_domain: Optional[str] = None  # Custom domain from domain manager
    
    def set_custom_domain(self, domain: str) -> None:
        """Set custom domain for burner emails"""
        self.custom_domain = domain
    
    def generate_burner_email(self, user_id: str, domain: Optional[str] = None) -> str:
        """
        Generate temporary email address
        Uses custom domain if available, otherwise uses default
        """
        if domain is None:
            domain = self.custom_domain or "opsecmail.onion"
        
        random_part = ''.join(random.choice(string.ascii_lowercase + string.digits) 
                             for _ in range(12))
        email = f"{random_part}@{domain}"
        
        self.burner_addresses[email] = {
            'user_id': user_id,
            'created_at': datetime.datetime.now(),
            'expires_at': datetime.datetime.now() + datetime.timedelta(hours=24)
        }
        
        return email
    
    def get_user_for_burner(self, email: str) -> Optional[str]:
        """Get user ID for burner email"""
        burner_info = self.burner_addresses.get(email)
        if burner_info and burner_info['expires_at'] > datetime.datetime.now():
            return burner_info['user_id']
        return None
    
    def cleanup_expired(self) -> None:
        """Remove expired burner addresses"""
        now = datetime.datetime.now()
        expired = [email for email, info in self.burner_addresses.items() 
                   if info['expires_at'] <= now]
        for email in expired:
            del self.burner_addresses[email]


# Global instances
email_storage = EmailStorage()
burner_manager = BurnerEmailManager()
