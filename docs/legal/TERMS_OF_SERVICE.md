# Terms of Service (ToS)

**Effective Date:** [To Be Determined]  
**Last Updated:** January 6, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Agreement to Terms

By accessing or using the opsechat service ("Service"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree to these Terms, do not use the Service.

**Important:** This Service is designed for privacy-preserving communications. However, privacy does not grant permission to engage in illegal activities. We will cooperate fully with law enforcement when illegal activity is detected.

---

## 2. Description of Service

### 2.1 What is opsechat?

opsechat is a privacy-focused anonymous communication platform that provides:
- **Anonymous Chat:** Ephemeral chat rooms over Tor hidden services
- **Secure Email:** End-to-end encrypted email with PGP support
- **Burner Emails:** Temporary disposable email addresses
- **Security Tools:** Email spoofing detection and phishing simulation (for education)

### 2.2 Key Features
- Tor-based anonymity
- Zero persistent storage (all data in memory only)
- Client-side encryption
- Ephemeral services (destroyed on restart)
- Open source and auditable

### 2.3 Technical Limitations
- Messages expire after 3 minutes (chat)
- Burner emails expire after 24 hours (default)
- No message history or persistent storage
- Keys cannot be recovered (by design)
- Service availability depends on Tor network

---

## 3. Eligibility

### 3.1 Age Requirement
You must be at least **18 years old** to use this Service. By using opsechat, you represent that you are 18 or older.

### 3.2 Legal Capacity
You must have the legal capacity to enter into binding contracts in your jurisdiction.

### 3.3 Jurisdictional Restrictions
This Service may not be available or legal in all jurisdictions. You are responsible for ensuring your use complies with local laws.

---

## 4. Account and Access

### 4.1 Registration
- Account creation will be required in the alpha release
- You must provide accurate information
- You are responsible for maintaining account security
- Free tier available initially

### 4.2 Session-Based Access
- Current implementation uses session-based identification
- Session data is ephemeral and destroyed on restart
- No persistent user profiles (by design)

### 4.3 Security Responsibilities
You are responsible for:
- Keeping your encryption keys secure
- Managing your passphrase/credentials
- Maintaining the security of your device
- Understanding that **we cannot recover lost keys**

---

## 5. Privacy and Data Handling

### 5.1 Zero-Disk Policy
We do **not** store your communications on disk:
- All data is in memory only
- Messages are automatically deleted after expiry
- No persistent chat logs
- No email archives (unless you save them locally)

### 5.2 What We Don't Have
- Your plaintext communications (we can't decrypt)
- Your IP address (hidden by Tor)
- Your browsing history
- Persistent user profiles
- Long-term message archives

### 5.3 What We May Have
Despite our privacy-first design, we may temporarily have:
- Session identifiers (random, temporary)
- Timestamps of service access
- Metadata (message counts, timing)
- Technical logs for debugging (minimal, short retention)

### 5.4 For More Information
See our [Privacy Policy](PRIVACY_POLICY.md) for complete details.

---

## 6. Encryption and Key Management

### 6.1 Client-Side Encryption
- All encryption happens in your browser
- We never see your private keys
- We cannot decrypt your messages
- You are solely responsible for key management

### 6.2 User-Provided Keys
- You can import your own PGP keys
- You can generate keys client-side
- Keys are stored in browser localStorage only
- **We cannot recover lost keys**

### 6.3 Key Security
You must:
- Keep your private keys secure
- Back up your keys safely
- Never share your private keys
- Understand that key loss means permanent data loss

---

## 7. Acceptable Use

### 7.1 Compliance with AUP
You must comply with our [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md), which prohibits:
- Illegal activities
- Abuse, harassment, or threats
- Spam or malicious content
- Fraud or deception
- Intellectual property violations
- System attacks or abuse

### 7.2 Content Restrictions
- **Allowed:** Text-based communications
- **Prohibited:** Videos, images (initially)
- **Future:** Limited attachment support (text-based only)

### 7.3 Consequences of Violation
- Immediate suspension or termination
- Reporting to law enforcement
- Legal action if necessary
- **No refunds** for paid services (when implemented)

---

## 8. Law Enforcement Cooperation

### 8.1 Our Position
**We are committed to privacy, but we will not protect criminals.**

If we receive valid legal process (warrant, subpoena, court order):
- We **will cooperate fully** with law enforcement
- We **will provide** any data or metadata available
- We **will not** notify you if legally prohibited
- We **will assist** investigations to the fullest extent possible

### 8.2 Data Limitations
Due to our privacy-preserving architecture:
- We have limited data to provide
- Encrypted content is inaccessible to us
- Messages may have already expired
- User identification may be difficult

### 8.3 Transparency
We will:
- Publish transparency reports (when feasible)
- Disclose legal requests (when legally allowed)
- Notify users of requests (when not prohibited)

---

## 9. Service Availability

### 9.1 No Guarantee of Availability
We provide the Service "as is" without guarantees of:
- Continuous availability
- Uninterrupted access
- Error-free operation
- Data persistence (by design!)

### 9.2 Service Changes
We may:
- Modify features at any time
- Add or remove functionality
- Change pricing (with notice)
- Discontinue the Service (with notice)

### 9.3 Tor Dependency
The Service depends on the Tor network:
- Tor outages affect service availability
- Tor can be blocked by networks or countries
- We have no control over Tor network performance

---

## 10. Intellectual Property

### 10.1 Our IP
- opsechat code is open source (MIT License)
- "opsechat" name and branding are owned by Hyperion Gray
- Documentation and design are copyrighted
- Third-party components retain their licenses

### 10.2 Your Content
You retain ownership of your communications, but:
- We have no access to encrypted content
- We don't store or claim ownership of your data
- You grant us right to transmit/process for service operation

### 10.3 Open Source
- Source code: https://github.com/HyperionGray/opsechat
- License: MIT (see LICENSE.md)
- Contributions welcome (see CONTRIBUTING.md)

---

## 11. Disclaimers and Limitations

### 11.1 "AS IS" Service
THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO:
- Merchantability
- Fitness for a particular purpose
- Non-infringement
- Security or accuracy
- Uninterrupted or error-free operation

### 11.2 Anonymity Limitations
We make reasonable efforts to preserve anonymity, but:
- Tor anonymity is not absolute
- Browser fingerprinting is possible
- Timing attacks may be feasible
- State actors may have deanonymization capabilities
- **We cannot guarantee absolute anonymity**

### 11.3 Encryption Limitations
Client-side encryption protects content, but:
- Metadata remains visible
- Timing information is observable
- Key compromise compromises messages
- Implementation bugs may exist
- **We cannot guarantee perfect security**

### 11.4 No Legal Advice
This Service does not provide legal advice. You are responsible for:
- Understanding laws in your jurisdiction
- Ensuring your use is lawful
- Accepting consequences of your actions

---

## 12. Limitation of Liability

### 12.1 Maximum Liability
TO THE MAXIMUM EXTENT PERMITTED BY LAW, HYPERION GRAY LLC AND ITS AFFILIATES, OFFICERS, EMPLOYEES, AGENTS, AND LICENSORS SHALL NOT BE LIABLE FOR:

- Any indirect, incidental, special, consequential, or punitive damages
- Loss of profits, data, use, goodwill, or other intangible losses
- Damages resulting from unauthorized access, alteration, or disclosure
- Damages resulting from Service downtime or unavailability
- Damages from third-party conduct or content

### 12.2 Liability Cap
In no event shall our total liability exceed the greater of:
- $100 USD, or
- Amounts paid by you in the past 12 months

### 12.3 Exceptions
Some jurisdictions don't allow limitation of implied warranties or liability for incidental or consequential damages. In such cases, our liability is limited to the maximum extent permitted by law.

---

## 13. Indemnification

You agree to indemnify, defend, and hold harmless Hyperion Gray LLC, its affiliates, officers, employees, agents, and licensors from any claims, losses, damages, liabilities, costs, and expenses (including reasonable attorneys' fees) arising from:
- Your use of the Service
- Your violation of these Terms
- Your violation of any rights of another party
- Your violation of applicable laws
- Content you transmit through the Service

---

## 14. Payment Terms (Future)

### 14.1 Free Tier
- Initially, the Service will be free
- Free tier may have usage limits
- No payment required for basic features

### 14.2 Paid Plans (Planned)
When paid plans are introduced:
- Pricing will be clearly disclosed
- Payment via cryptocurrency (for privacy)
- No refunds for service termination due to AUP violations
- 30-day money-back guarantee otherwise

### 14.3 Changes to Pricing
- Free tier users: 30 days notice of changes
- Paid users: Grandfathered for current billing cycle
- No retroactive price increases

---

## 15. Termination

### 15.1 By You
You may stop using the Service at any time:
- No notice required
- Data is automatically deleted (ephemeral by design)
- Delete your keys from browser storage

### 15.2 By Us
We may suspend or terminate your access:
- Immediately for AUP violations
- Immediately for illegal activity
- With 30 days notice for service discontinuation
- With notice for payment issues (when applicable)

### 15.3 Effect of Termination
Upon termination:
- Your access to the Service ends immediately
- All ephemeral data is automatically deleted
- No data retention (by design)
- No refunds for paid services (when applicable)

---

## 16. Dispute Resolution

### 16.1 Governing Law
These Terms are governed by the laws of [jurisdiction TBD], without regard to conflict of law principles.

### 16.2 Arbitration
Any disputes shall be resolved through binding arbitration in accordance with [arbitration rules TBD], except:
- Small claims court actions
- Injunctive relief
- Intellectual property disputes

### 16.3 Class Action Waiver
You agree to resolve disputes individually and waive any right to participate in class actions or representative proceedings.

### 16.4 Exceptions
Some jurisdictions don't allow arbitration agreements. In such cases, disputes shall be resolved in the courts of [jurisdiction TBD].

---

## 17. Miscellaneous

### 17.1 Entire Agreement
These Terms, together with our Acceptable Use Policy and Privacy Policy, constitute the entire agreement between you and Hyperion Gray LLC.

### 17.2 Severability
If any provision is found unenforceable, it shall be modified to the minimum extent necessary, and other provisions remain in full force.

### 17.3 No Waiver
Failure to enforce any provision does not waive our right to enforce it later.

### 17.4 Assignment
You may not assign these Terms. We may assign these Terms to any affiliate or successor.

### 17.5 Force Majeure
We are not liable for delays or failures due to circumstances beyond our reasonable control.

---

## 18. Changes to Terms

### 18.1 Modification Rights
We reserve the right to modify these Terms at any time.

### 18.2 Notice of Changes
- Posted to website and repository
- Email notice (if we have your email)
- 30 days before effective date
- Immediate for legal/security reasons

### 18.3 Acceptance of Changes
Continued use after changes constitutes acceptance. If you don't agree, stop using the Service.

---

## 19. Contact Information

**Hyperion Gray LLC**

- **Website:** https://www.hyperiongray.com
- **Email:** [TBD]
- **Repository:** https://github.com/HyperionGray/opsechat
- **Security Issues:** See SECURITY.md
- **Abuse Reports:** See ACCEPTABLE_USE_POLICY.md

---

## 20. Acknowledgment and Acceptance

**BY USING OPSECHAT, YOU ACKNOWLEDGE THAT:**

1. You have read and understood these Terms of Service
2. You agree to be bound by these Terms
3. You are 18 years or older
4. You will use the Service lawfully and ethically
5. You understand the technical limitations
6. You accept the risks of anonymous communication
7. You will not use the Service for illegal activities
8. You understand we will cooperate with law enforcement
9. You are responsible for your encryption keys
10. You accept that data loss is permanent (by design)

**Violation of these Terms may result in legal consequences.**

---

## Legal Notices

### Alpha Release
This Service is in **alpha testing**. It may contain bugs, security issues, or unexpected behavior. Use at your own risk.

### No Warranty
WE PROVIDE NO WARRANTY, EXPRESS OR IMPLIED. THE SERVICE IS PROVIDED "AS IS."

### Use at Your Own Risk
YOU ASSUME ALL RISKS ASSOCIATED WITH USING THIS SERVICE.

### Not a Substitute for Legal Advice
CONSULT A LAWYER IF YOU HAVE QUESTIONS ABOUT YOUR LEGAL OBLIGATIONS.

---

**Last Updated:** January 6, 2026  
**Version:** 1.0 (Draft - Alpha Release)

---

*This is a template document. Legal review and customization are required before production use.*

**TODO before alpha:**
- [ ] Legal counsel review and approval
- [ ] Determine jurisdiction and governing law
- [ ] Set up arbitration procedures
- [ ] Add contact information
- [ ] Integrate with UI (checkbox acknowledgment)
- [ ] Publish privacy policy
- [ ] Set effective date
- [ ] Translate to other languages (if needed)
- [ ] Add dispute resolution contact information
