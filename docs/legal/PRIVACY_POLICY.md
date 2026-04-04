# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** April 4, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Summary

opsechat is built for privacy-preserving communication with minimal data retention.
Core behavior:

- In-memory processing for chat and message workflows
- Automatic message expiry
- No long-term user profile storage in the current architecture
- Tor-first access model for network anonymity

This policy explains what data may exist temporarily and how it is handled.

---

## 2. Data We Process

### 2.1 Data You Provide

- Chat and direct-message content you submit
- Optional email content you compose through the service
- Optional settings or form input during active sessions

### 2.2 Operational Metadata

To keep the service functional and secure, we may process:

- Temporary session identifiers
- Request timing and endpoint usage patterns
- Rate-limit counters
- Minimal error/debug telemetry

### 2.3 Data We Intentionally Avoid Collecting

- Persistent identity profiles by default
- Long-term plaintext communication archives
- Non-essential behavioral tracking

---

## 3. Storage and Retention

### 3.1 Ephemeral Retention

Most user-generated communication is designed to expire quickly:

- Chat messages are automatically deleted on short timers
- Direct messages expire automatically
- Temporary runtime state is cleared on service restart

### 3.2 No Guaranteed Recovery

Because storage is intentionally minimal and ephemeral:

- Deleted content is not recoverable through product features
- Lost cryptographic keys cannot be restored by the service

---

## 4. Encryption and Security

- Transport and routing are designed for secure communication patterns
- Client-side encryption options are available for message confidentiality
- Server-side controls include rate limiting and security headers
- Access is intended for lawful privacy use only

No system can provide perfect security; users remain responsible for endpoint security and key management.

---

## 5. Cookies and Local Data

The service may use essential session mechanisms required for operation.
These are used for runtime behavior (for example, rate limiting and session continuity), not behavioral advertising.

Client-side tools may store data in browser storage when users choose encryption features.

---

## 6. Third Parties

Depending on deployment and configuration, service operation may rely on third-party infrastructure (for example Tor network components, hosting, DNS/domain vendors, or email transport providers).

These providers may process operational metadata under their own policies.

---

## 7. Legal Requests and Abuse Handling

opsechat is privacy-focused, but not a shield for unlawful behavior.
When legally required, the operator may respond to valid legal process and abuse investigations.

Because retention is intentionally limited, available records may be minimal.

---

## 8. Your Responsibilities

You are responsible for:

- Lawful use of the service
- Protecting your own devices and credentials
- Safeguarding and backing up your own encryption keys
- Reviewing the [Terms of Service](TERMS_OF_SERVICE.md) and [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md)

---

## 9. Policy Changes

This policy may be updated as the product architecture evolves.
Material changes should be published with an updated date.

---

## 10. Contact

For privacy inquiries, use project support/security channels documented in repository materials.

---

*This document is a technical policy draft for alpha operations and should receive legal review before production launch.*
