# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** March 27, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Overview

This Privacy Policy explains what information opsechat may process, how long it is retained, and the limits of what we can access.

opsechat is designed around ephemeral communication and minimal retention. The system prioritizes in-memory operation and short-lived data.

---

## 2. Data We Intentionally Minimize

By design, opsechat does not maintain traditional long-term user profiles or message archives.

The service architecture is intended to avoid persistent storage of:
- Chat message history
- Long-lived communication logs
- Plaintext message content at rest
- Permanent account analytics (current alpha implementation)

---

## 3. Data We May Process

To provide service functionality, opsechat may temporarily process:
- Session identifiers
- Message metadata (timestamps, size, room identifiers)
- Temporary in-memory message content
- Error and operational diagnostics

For encrypted chat features, encrypted payloads may be relayed without server-side decryption.

---

## 4. Retention Model

Current default behavior includes:
- Chat messages: short-lived, auto-expiring (minutes)
- Direct messages: short-lived, auto-expiring (minutes)
- Temporary service state: cleared on restart

Because most data is ephemeral, some information may no longer exist when requests (including legal requests) are received.

---

## 5. Legal Basis and Compliance

We process only the minimum data required to operate and secure the service.

Where required by law, we may process and disclose available information to comply with:
- Court orders
- Subpoenas
- Other valid legal process

We do not claim immunity from legal obligations.

---

## 6. Security Practices

Security controls include:
- Strict security headers
- Input validation and sanitization
- Rate limiting on sensitive endpoints
- In-memory cleanup routines for ephemeral content

No system is perfectly secure. Users should assume risk and apply their own operational safeguards.

---

## 7. Third Parties

opsechat may rely on infrastructure or platform providers. Their services have separate privacy policies and data handling practices.

When users access opsechat through Tor or other network tooling, those tools have their own threat models and privacy characteristics.

---

## 8. User Rights (Planned Expansion)

As account-based features mature, this policy will be expanded to describe:
- Access/export requests
- Deletion requests
- Jurisdiction-specific rights
- Contact channels for privacy requests

---

## 9. Changes to This Policy

We may update this policy as features or legal obligations change.

Material updates will be published in the repository and reflected in the "Last Updated" field.

---

## 10. Contact

For privacy inquiries, contact details will be added before production launch.

Until then, use the project repository for non-sensitive policy questions:
- https://github.com/HyperionGray/opsechat

---

## Draft Status

This document is a release-readiness draft and still requires legal review before production deployment.
