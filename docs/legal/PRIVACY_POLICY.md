# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** April 8, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Overview

This Privacy Policy explains how opsechat handles information when you use the service. Opsechat is built around ephemeral, memory-only operation and aims to minimize retained data.

This is a draft policy for alpha release and requires legal review before production.

---

## 2. Key Privacy Principles

- Data minimization by default
- In-memory processing where possible
- Automatic expiration of short-lived communications
- No routine retention of plaintext chat history
- Client-side encryption support

---

## 3. Data We Process

Depending on features you use, opsechat may process:

- Session identifiers used to maintain a temporary session
- Chat and direct message content while active in memory
- Service metadata (timestamps, endpoint usage counts, and rate-limit counters)
- Optional email configuration and email content if you use email features
- Operational logs needed to keep the service running and secure

---

## 4. Data We Do Not Intentionally Collect

Opsechat is designed to avoid collecting long-lived user profiles. We do not intentionally build behavioral tracking profiles or advertising audiences.

Because the service may run behind Tor and ephemeral infrastructure, persistent identifiers are intentionally limited.

---

## 5. How Long Data Is Retained

- Chat messages are ephemeral and expire automatically (for example, 3-minute windows in current chat implementation).
- Direct messages are short-lived and expire quickly (for example, 1-minute windows in current DM implementation).
- In-memory rate-limit and session structures are periodically cleaned.
- Some operational logs may exist temporarily for reliability and abuse prevention.

Retention periods can change as product requirements evolve. Material changes should be reflected in this document.

---

## 6. Legal Basis and Service Operation

We process limited data to:

- Provide core service functionality
- Keep the service secure and available
- Enforce abuse controls and policy restrictions
- Comply with legal obligations

---

## 7. Security Measures

Current controls include:

- Content Security Policy and hardening headers
- Endpoint rate limiting
- Input validation and sanitization
- Ephemeral data handling for chat/DM features
- Optional end-to-end encryption paths for supported flows

No system can guarantee absolute security. Users should assume threat models include endpoint compromise and metadata exposure.

---

## 8. Third-Party Services

Deployments may rely on infrastructure providers (for hosting, DNS, or cloud services). These providers may process operational metadata according to their own privacy terms.

If you integrate external mail providers, those systems are governed by their own policies.

---

## 9. Law Enforcement and Legal Requests

Where legally required, we may disclose information available to us in response to valid legal process. Due to ephemeral design, available data may be limited.

See also:
- [Terms of Service](TERMS_OF_SERVICE.md)
- [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md)

---

## 10. Cross-Border Data Use

Service components may run in multiple jurisdictions depending on deployment architecture. Applicable laws and data obligations may vary by region.

---

## 11. Your Choices

Depending on deployment and feature set, you may be able to:

- Limit what you share through the service
- Avoid optional feature integrations
- Use short-lived sessions
- Stop using the service at any time

---

## 12. Policy Changes

We may update this policy as features and legal requirements evolve. The "Last Updated" date will be revised when substantive updates are made.

---

## 13. Contact

**Hyperion Gray LLC**  
Website: https://www.hyperiongray.com  
Repository: https://github.com/HyperionGray/opsechat

---

*Draft notice: legal counsel review is required prior to production rollout.*
