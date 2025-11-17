# Real Email System - Quick Start Guide

## Overview

OpSechat now supports **real email sending and receiving** via SMTP/IMAP, along with automated domain purchasing for burner email rotation.

## Quick Setup

### 1. Configure SMTP (For Sending Emails)

Navigate to: `http://yourservice.onion/{path}/email/config`

#### Gmail Setup
```
SMTP Server: smtp.gmail.com
Port: 587
Username: your-email@gmail.com
Password: [App Password - not your regular password]
TLS: ✓ Checked
```

**Getting Gmail App Password:**
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Go to App Passwords
4. Generate new app password for "Mail"
5. Use that password in the configuration

#### ProtonMail Setup
```
SMTP Server: smtp.protonmail.com
Port: 587
Username: your-email@protonmail.com
Password: [Your ProtonMail password]
TLS: ✓ Checked
```

**Note:** ProtonMail requires Bridge for SMTP access.

### 2. Configure IMAP (For Receiving Emails)

Navigate to: `http://yourservice.onion/{path}/email/config`

#### Gmail Setup
```
IMAP Server: imap.gmail.com
Port: 993
Username: your-email@gmail.com
Password: [Same App Password as SMTP]
SSL: ✓ Checked
```

#### ProtonMail Setup
```
IMAP Server: imap.protonmail.com
Port: 993
Username: your-email@protonmail.com
Password: [ProtonMail Bridge password]
SSL: ✓ Checked
```

### 3. Configure Domain API (Optional - For Burner Email Rotation)

#### Get Porkbun API Credentials
1. Create account at https://porkbun.com
2. Go to https://porkbun.com/account/api
3. Generate API keys

#### Configure in OpSechat
```
API Key: pk1_xxxxxxxxxxxxxxxxx
API Secret: sk1_xxxxxxxxxxxxxxxxx
Monthly Budget: $50.00
```

**Budget Notes:**
- System will find domains under $5 (typically .xyz, .club, .online)
- Budget prevents overspending
- Visual progress bar shows spending

#### Rotate to New Domain
1. Click "Rotate to New Domain" button
2. System finds cheapest available domain
3. Purchases automatically if within budget
4. New burner emails use purchased domain

## Using the Email System

### Sending an Email

1. Navigate to: `http://yourservice.onion/{path}/email/compose`
2. Fill in email details:
   - From: your-email@example.com
   - To: recipient@example.com
   - Subject: Your subject
   - Message: Your message (supports PGP)
3. Check "Send via SMTP (real email)" if configured
4. Click "Send Email"

**Result:**
- If SMTP configured and checked: Email sent to real recipient
- Always saved to local inbox for reference

### Receiving Emails

1. Navigate to: `http://yourservice.onion/{path}/email/config`
2. Click "Fetch Latest Emails" or "Fetch Unread Only"
3. View emails at: `http://yourservice.onion/{path}/email`

**Features:**
- HTML emails shown as plain text
- Images shown as `[Image: filename.jpg]`
- PGP encrypted messages preserved
- All headers visible

### Generating Burner Email

1. Navigate to: `http://yourservice.onion/{path}/email/burner`
2. Click "Generate Burner Email"
3. Use generated address: `random123@domain.xyz`
4. Emails sent to this address appear in your inbox

**With Custom Domain:**
- Configure Porkbun API first
- Rotate to purchase domain
- Burner emails use your purchased domain

## Security Features

### Plain Text Only
- HTML emails rendered as text (not executed)
- Images shown as text placeholders: `[Image: photo.jpg - image/jpeg]`
- Prevents XSS and tracking pixels
- Allows analysis of raw content

### PGP Support
- Paste encrypted PGP message in compose form
- PGP content bypasses sanitization
- Preserved in SMTP sending
- Detected in IMAP receiving

### In-Memory Credentials
- SMTP/IMAP passwords stored in RAM only
- Lost when server restarts
- Never written to disk
- Re-configure each session

### Budget Control
- Prevents runaway domain spending
- Visual progress bar
- Configurable monthly limit
- Only purchases within budget

## Troubleshooting

### SMTP Not Working
- **Gmail:** Use App Password, not regular password
- **2FA Required:** Enable 2-Step Verification first
- **Less Secure Apps:** Not needed with App Passwords
- **ProtonMail:** Requires ProtonMail Bridge

### IMAP Not Working
- **Gmail:** Enable IMAP in settings
- **Same Password:** Use same App Password as SMTP
- **Firewall:** Port 993 must be open

### Domain Purchase Failed
- **Budget:** Check if budget exceeded
- **API Keys:** Verify correct pk1_ and sk1_ keys
- **Domain Taken:** System tries multiple times
- **Porkbun Issues:** Check Porkbun account status

### Email Not Appearing
- **IMAP:** Click "Fetch Latest Emails" manually
- **No Auto-Sync:** Must fetch manually each time
- **Session:** Each browser session has separate inbox

## Advanced Features

### Raw Mode Email Editing
1. Compose email
2. Toggle "Raw Mode"
3. Edit headers directly:
```
From: sender@example.com
To: recipient@example.com
Subject: Test
X-Custom-Header: MyValue
X-Priority: High

Email body here...
```
4. Send via SMTP or save locally

### Security Testing
- **Spoofing Test:** Test domain lookalikes
- **Phishing Simulation:** Training emails
- **Header Injection:** Test custom headers

## Example Workflows

### Workflow 1: Anonymous Communication
1. Configure Porkbun API with budget
2. Rotate to purchase cheap domain ($2-3)
3. Generate burner email: `abc123@randomdomain.xyz`
4. Share burner address
5. Fetch emails from IMAP periodically
6. Reply using PGP encryption

### Workflow 2: Security Testing
1. Configure SMTP with test account
2. Compose email in Raw Mode
3. Add custom headers for testing
4. Send to test target
5. Analyze results

### Workflow 3: Privacy Suite
1. Use Tor Browser to access
2. Configure ProtonMail SMTP/IMAP
3. Generate burner email
4. Communicate with PGP encryption
5. All traffic through Tor
6. No data on disk

## Performance Notes

- **IMAP Fetch:** Can be slow for large inboxes
- **Limit Emails:** Use limit parameter (default 10)
- **Unread Only:** Faster than fetching all
- **Budget Tracking:** Resets on server restart

## Privacy Considerations

1. **SMTP/IMAP Credentials**
   - Stored in memory only
   - Lost on restart
   - Consider dedicated email account

2. **Domain Purchases**
   - Registered to your Porkbun account
   - Public WHOIS (consider privacy protection)
   - Use privacy registration when available

3. **Email Content**
   - Local inbox in memory only
   - Not encrypted unless using PGP
   - Lost on server restart

4. **Tor Integration**
   - All web access through Tor
   - SMTP/IMAP traffic NOT through Tor
   - Email provider sees your real IP

## Support

For issues or questions:
- Check [EMAIL_SYSTEM.md](EMAIL_SYSTEM.md) for full documentation
- Review [SECURITY.md](SECURITY.md) for security best practices
- Submit GitHub issues with detailed descriptions

## License

Same as opsechat - see LICENSE file.

---

**Remember:** This is a security research tool. Use responsibly and ethically. Always obtain proper authorization before testing systems you don't own.
