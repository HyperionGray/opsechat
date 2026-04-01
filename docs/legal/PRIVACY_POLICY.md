# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** April 1, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Scope

This Privacy Policy explains what information opsechat processes, how we use it, and your options.

opsechat is designed to minimize retained data by default:
- In-memory processing
- Ephemeral chat and message retention
- Privacy-preserving transport assumptions (Tor-first usage)

---

## 2. Data We Process

### 2.1 Session Data
- Anonymous session identifiers
- Temporary UI/session preferences
- Short-lived operational state required to provide service features

### 2.2 Message and Communication Data
- Chat and direct-message content while active in memory
- Email content while active in memory for configured flows
- Message metadata required for routing, expiry, and abuse controls

### 2.3 Security and Operational Data
- Rate-limit counters
- Minimal service health metadata
- Temporary debug/operational logs when enabled

### 2.4 Data We Do Not Intend to Retain Long-Term
- Persistent plaintext chat history
- Long-term profile records for anonymous sessions
- Permanent storage of ephemeral messages by default

---

## 3. Why We Process Data

We process only the data needed to:
- Deliver core messaging and email functionality
- Enforce security controls (rate limits, abuse mitigation)
- Maintain service integrity and availability
- Investigate abuse and comply with legal obligations

---

## 4. Retention

Retention is intentionally short where technically feasible:
- Ephemeral chat messages: auto-expire by service policy
- Burner email entries: expire automatically by service policy
- Session metadata: retained only as needed for active operation

Operational and legal exceptions may apply for:
- Abuse investigations
- Security incident response
- Valid legal requests

---

## 5. Security Practices

We use a defense-in-depth approach including:
- Strict response security headers
- Input validation and sanitization
- Rate limiting and abuse controls
- Minimal-data architecture where possible

No system is perfectly secure. Use appropriate operational security practices.

---

## 6. Legal Compliance and Requests

We may disclose available data when required by valid legal process.

Because of privacy-preserving architecture choices, available records may be limited and time-bounded.

---

## 7. Your Choices

You can reduce your exposure by:
- Avoiding personal identifiers in messages
- Using Tor and privacy-focused clients
- Not sharing sensitive secrets in plaintext
- Rotating burner identifiers and credentials

Where account-based features are introduced, additional controls may be provided.

---

## 8. Policy Changes

We may update this Privacy Policy to reflect:
- Product and architecture changes
- Legal requirements
- Security improvements

When materially updated, the new version date will be reflected above.

---

## 9. Contact

For privacy questions:
- Repository: https://github.com/HyperionGray/opsechat
- Security process: see `SECURITY.md`

---

*This document is an operational privacy policy draft and should receive legal review before production launch.*
