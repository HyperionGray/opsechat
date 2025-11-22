# Email System Documentation

## Overview

The OpSec Email System provides an encrypted, anonymous email platform integrated with the opsechat Tor hidden service. This system includes **real SMTP/IMAP email integration** for sending and receiving actual emails, along with automated domain purchasing for burner email rotation.

**NEW:** Real email capabilities with SMTP/IMAP support and automated domain management!

## ⚠️ Security Notice

**FOR SECURITY RESEARCH AND AUTHORIZED TESTING ONLY**

This tool includes features for email spoofing and security testing. These capabilities are intended solely for:
- Authorized penetration testing
- Security research
- Defensive security training
- Phishing awareness training

Misuse of these features may be illegal in your jurisdiction. Always obtain proper authorization before testing.

## Core Features

### 1. Real Email Integration (NEW!)

#### SMTP Email Sending
- Send real emails to external addresses
- TLS/SSL encryption support
- Custom header support for security testing
- PGP encrypted message support
- Plain text only (no HTML rendering)

**Configuration:** Configure SMTP settings at `/{path}/email/config`

Supported providers:
- Gmail (smtp.gmail.com:587)
- ProtonMail (smtp.protonmail.com:587)
- Outlook (smtp.office365.com:587)
- Any custom SMTP server

#### IMAP Email Receiving
- Fetch emails from real email accounts
- SSL/TLS encryption support
- Plain text extraction (HTML converted to text)
- Image attachments shown as text placeholders
- Unread/all email filtering
- PGP encrypted message detection

**Configuration:** Configure IMAP settings at `/{path}/email/config`

### 2. Automated Domain Management (NEW!)

#### Porkbun API Integration
- Automatic domain availability checking
- Purchase cheap domains (.xyz, .club, .online, etc.)
- Monthly budget tracking
- Domain rotation for burner emails

**Configuration:** Add Porkbun API credentials at `/{path}/email/config`
- Get API keys from: https://porkbun.com/account/api
- Set monthly budget (default: $50)
- System finds domains under $5

#### Budget Management
- Track spending across domain purchases
- View received emails with full header information
- PGP encrypted message detection and display
- In-memory storage (nothing touches disk unencrypted)
- JavaScript optional interface
- Tor-compatible anonymous access

**Access:** `/{path}/email`

### 2. Email Composition
- **Standard Mode:** Simple form-based email composition
- **Raw Mode:** Full control over email headers and structure
- PGP encrypted message support
- Custom header injection for security testing

**Access:** `/{path}/email/compose`

#### Standard Mode
Use the standard compose form to create emails with basic fields:
- From address
- To address
- Subject
- Message body

#### Raw Mode
Toggle to raw mode for advanced features:
- Direct header editing (From, To, Subject, CC, BCC, etc.)
- Custom X- headers for testing
- Full email structure control
- Test email spoofing scenarios

**Example Raw Email:**
```
From: sender@example.com
To: recipient@example.com
Subject: Test Email
X-Custom-Header: Testing
X-Priority: High

This is the email body.
```

### 3. Email Viewing
- Detailed email display with all headers
- PGP encryption badge for encrypted messages
- Additional headers collapsible section
- One-click access to edit or delete

**Access:** `/{path}/email/view/{email_id}`

### 4. Raw Mode Editing
- Edit existing emails in raw mode
- Modify headers and body content
- Test email structure variations
- Security research on email parsing

**Access:** `/{path}/email/edit/{email_id}`

### 5. Modern Burner Email System (Enhanced!)
Modern, Guerrillamail-style rotating anonymous email system with advanced features:

- **Multi-Burner Management** - Keep multiple active burner emails simultaneously
- **Live Countdown Timers** - Real-time expiry tracking with JavaScript enabled
- **Quick Rotation** - One-click generation of new addresses
- **Smart Rotation** - Rotate existing burners (generates new, expires old)
- **Instant Copy** - One-click copy to clipboard
- **Stats Dashboard** - Track active burner count and total time remaining
- **Visual Indicators** - Color-coded warnings when burners are expiring soon
- **Manual Expiry** - Delete burners before they expire
- **No Login Required** - Instant anonymous email addresses
- **24-Hour Validity** - Configurable expiry periods
- **Auto-Cleanup** - Expired burners automatically removed
- **Tor-Compatible** - Works seamlessly over Tor network

**Access:** `/{path}/email/burner` (NoScript) or `/{path}/email/burner/yesscript` (JavaScript)

**Key Features:**
- Generate unlimited burner addresses
- Each user can have multiple active burners
- Real-time countdown updates (with JavaScript)
- Direct link to inbox from each burner
- Custom domain support (via Porkbun integration)

- Prevent over-spending with configurable limits
- Visual budget bar showing spending vs. limit
- Auto-rotation when budget allows

### 3. Email Inbox
- View received emails with full header information
- PGP encrypted message detection and display
- In-memory storage (nothing touches disk unencrypted)
- JavaScript optional interface
- Tor-compatible anonymous access
- Fetch from IMAP button for real email sync

**Access:** `/{path}/email`

### 4. Email Composition
- **Standard Mode:** Simple form-based email composition
- **Raw Mode:** Full control over email headers and structure
- **Real SMTP Sending:** Optional checkbox to send via configured SMTP
- PGP encrypted message support
- Custom header injection for security testing

**Access:** `/{path}/email/compose`

#### Standard Mode
Use the standard compose form to create emails with basic fields:
- From address
- To address
- Subject
- Message body
- Optional SMTP sending (when configured)

#### Raw Mode
Toggle to raw mode for advanced features:
- Direct header editing (From, To, Subject, CC, BCC, etc.)
- Custom X- headers for testing
- Full email structure control
- Test email spoofing scenarios
- Optional SMTP sending (when configured)

### In-Memory Storage
All emails are stored in memory only. The system implements a two-key encryption approach:
- **Master Key:** Password-protected asymmetric encryption for user authentication
- **Email Key:** Used for encrypting email content

Data flow:
```
Compose → In-Memory Storage → Optional PGP Encryption → Display
```

### PGP Support
The system integrates with existing PGP functionality:
- Detects PGP encrypted messages (`-----BEGIN PGP MESSAGE-----`)
- Bypasses sanitization for PGP content
- Preserves encrypted message integrity
- Displays encryption status in UI

### Security Features
- **Header Injection Protection:** Newlines and control characters removed
- **Email Validation:** Regex-based address validation
- **Sanitization Bypass:** PGP messages bypass HTML/script sanitization
- **Session Isolation:** Each user gets isolated inbox
- **No Disk Persistence:** All data in-memory unless explicitly encrypted

## API Reference

### Email Storage Class
```python
class EmailStorage:
    def create_user_inbox(user_id: str) -> None
    def add_email(user_id: str, email: Dict) -> None
    def get_emails(user_id: str, limit: Optional[int]) -> List[Dict]
    def get_email(user_id: str, email_id: str) -> Optional[Dict]
    def delete_email(user_id: str, email_id: str) -> bool
    def update_email(user_id: str, email_id: str, updated: Dict) -> bool
```

### Email Composer Class
```python
class EmailComposer:
    @staticmethod
    def create_email(from_addr, to_addr, subject, body, headers) -> Dict
    
    @staticmethod
    def parse_raw_email(raw_content: str) -> Dict
    
    @staticmethod
    def format_raw_email(email: Dict) -> str
```

### Burner Email Manager
```python
class BurnerEmailManager:
    def generate_burner_email(user_id: str, domain: str) -> str
    def get_user_for_burner(email: str) -> Optional[str]
    def cleanup_expired() -> None
```

## Testing

The email system includes comprehensive tests:

```bash
# Run email system tests
PYTHONPATH=. pytest tests/test_email_system.py -v

# Run all tests
PYTHONPATH=. pytest tests/ -v
```

Test coverage includes:
- Email storage operations (create, read, update, delete)
- Email validation and sanitization
- Email composition and parsing
- Burner email generation and expiry
- PGP message detection

## Future Enhancements

### Planned Features
The following features are planned for future releases:

#### 1. SMTP/IMAP Integration
- Custom SMTP server settings
- Send emails to external addresses
- Receive emails from external sources
- Multiple protocol support (SMTP, IMAP, POP3)

#### 2. Database Backend
- HBase integration for scalability
- Persistent email storage with encryption
- Query optimization for large inboxes
- Backup and recovery features

#### 3. Spoofing Detection & Testing
- Test email domains for spoofing vulnerabilities
- Automated spoofing attempts
- SPF/DKIM/DMARC validation testing
- Subdomain spoofing detection
- Unicode spoofing attempts (lookalike domains)

#### 4. Phishing Simulation
- Persistent attack mode for training
- "YOU JUST GOT OWNED" warnings
- Gamification features
- Phishing awareness metrics
- Custom phishing templates

#### 5. Automated Detection
- Spam/scam email detection
- Automated OSINT on suspicious emails
- Geo-location detection for scammers
- Threat intelligence integration
- Malicious link detection

#### 6. Penetration Testing Tools
- Website cloning for phishing tests
- Lookalike domain suggestions
- Payload encryption/encoding tools
- RTLO (Right-to-Left Override) attacks
- Unicode lookalike character attacks
- HTML5/JavaScript geo-grabbing
- Image-based tracking pixels
- Custom header injection testing

#### 7. Domain Management
- API integration (Porkbun, etc.)
- Automatic domain purchasing
- Budget management (monthly limits)
- Domain rotation system
- Blacklist testing against popular sites
- Automatic domain switching

#### 8. Advanced Features
- Email templates library
- Bulk email operations
- Email search and filtering
- Attachment support (encrypted)
- Calendar integration
- Contact management
- Email aliases
- Forwarding rules

## Usage Examples

### Example 1: Basic Email Composition
1. Navigate to `/{path}/email/compose`
2. Fill in From, To, Subject, and Body
3. Click "Send Email"
4. Email appears in inbox

### Example 2: Raw Mode Email with Custom Headers
1. Navigate to `/{path}/email/compose`
2. Toggle to "Raw Mode"
3. Enter:
```
From: security@test.com
To: target@example.com
Subject: Security Test
X-Mailer: CustomMailer
X-Priority: 1

This is a test email for security research.
```
4. Click "Send Email"

### Example 3: PGP Encrypted Email
1. Navigate to `/{path}/email/compose`
2. In the body field, paste your PGP encrypted message:
```
-----BEGIN PGP MESSAGE-----
Version: OpenPGP.js

wcBMA1234567890ABC
...encrypted content...
-----END PGP MESSAGE-----
```
3. Send normally - PGP content is preserved

### Example 4: Modern Burner Email System
#### Generating Multiple Burners
1. Navigate to `/{path}/email/burner`
2. Click "Generate New Burner Email" multiple times
3. View all active burners with countdown timers
4. Each burner shows:
   - Email address with copy button
   - Creation and expiry timestamps
   - Time remaining (live countdown with JS)
   - Quick action buttons

#### Using the Rotation Feature
1. From the burner list, click "🔄 Rotate (Generate New)" on any burner
2. This will:
   - Generate a new burner email
   - Immediately expire the old one
   - Keep your active burner count consistent

#### Managing Burners
- **Copy Email**: One-click copy to clipboard for easy sharing
- **View Inbox**: Direct link to your email inbox
- **Rotate**: Generate new and expire current in one action
- **Delete Now**: Manually expire before 24-hour limit

#### With JavaScript Enabled
1. Navigate to `/{path}/email/burner/yesscript`
2. Watch live countdown timers update every second
3. Visual warnings when burners are expiring soon (<1 hour)
4. Auto-refresh keeps burner list current

### Example 5: Legacy Burner Email (Simple)
1. Navigate to `/{path}/email/burner`
2. Click "Generate Burner Email"
3. Copy the generated address
4. Use for anonymous registration/communication
5. Check `/{path}/email` for incoming messages

## Troubleshooting

### Issue: Emails not appearing
- **Solution:** Refresh the inbox page. With JavaScript enabled, auto-refresh occurs every 30 seconds.

### Issue: PGP messages not displaying correctly
- **Solution:** Ensure the entire PGP block is included, starting with `-----BEGIN PGP MESSAGE-----`

### Issue: Cannot edit email headers
- **Solution:** Use Raw Mode editing (`/{path}/email/edit/{email_id}`)

### Issue: Burner email expired
- **Solution:** Generate a new burner email. Default expiry is 24 hours.

## Security Best Practices

1. **Authorization:** Always obtain written permission before testing email systems
2. **Ethical Use:** Use spoofing features only for authorized security testing
3. **Data Protection:** Remember that emails are stored in-memory and will be lost on server restart
4. **PGP Usage:** Use PGP encryption for sensitive communications
5. **Tor Browser:** Access via Tor Browser for maximum anonymity
6. **Burner Rotation:** Regularly generate new burner addresses
7. **Header Caution:** Be careful when editing raw headers - improper formatting may cause issues

## Integration with Chat System

The email system is fully integrated with the existing opsechat interface:
- Access from chat page via "📧 Email Inbox" link
- Shared session management
- Consistent styling and user experience
- Works with or without JavaScript
- Same Tor hidden service

## Contributing

When adding features to the email system:
1. Maintain JavaScript-optional functionality
2. Follow existing code patterns in `runserver.py`
3. Add tests to `tests/test_email_system.py`
4. Update this documentation
5. Ensure Tor compatibility
6. Keep in-memory storage as default

## License

Same as opsechat - see LICENSE file.

## Support

For issues or questions:
- Check existing GitHub issues
- Review SECURITY.md for security concerns
- Submit new issues with detailed descriptions

---

**Remember:** This is a security research tool. Use responsibly and ethically. Always obtain proper authorization before testing systems you don't own.
