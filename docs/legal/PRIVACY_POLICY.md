# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** April 4, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Overview

This Privacy Policy explains what information opsechat handles, how it is used, and what privacy limitations exist.

opsechat is designed to minimize retained data through ephemeral, in-memory operation and short message lifetimes.

---

## 2. Core Privacy Model

### 2.1 Ephemeral by Design

- Chat messages and direct messages are stored in memory only
- Messages auto-expire and are overwritten in memory before removal
- The service does not maintain long-term chat archives
- Service instances are intended to be disposable

### 2.2 Zero-Disk Intent

The core chat/email runtime is intended to avoid writing communications to disk. Operational artifacts (for example service logs or container metadata) may still exist at the host/platform layer depending on deployment configuration.

### 2.3 Tor and Network Privacy

When used over Tor hidden services:

- Participants can reduce IP exposure
- Onion routing provides transport-layer privacy benefits
- Metadata privacy is improved, but not absolute

---

## 3. Information We May Process

Depending on feature usage and deployment mode, the service may process:

- Random session identifiers
- Message payloads (stored in memory while active)
- Timestamps and message counters
- Transient operational diagnostics for reliability/security

For optional email integrations, configured SMTP/IMAP/account settings are processed to provide email functionality.

---

## 4. Information We Do Not Intend to Retain

- Persistent plaintext chat history
- Permanent user profiles for core anonymous chat use
- Long-term message archives as part of the default runtime

If you export, copy, or screenshot data locally, that data exists outside opsechat’s in-memory lifecycle and is under your control.

---

## 5. Security Controls

opsechat applies multiple security controls, including:

- Strict HTTP security headers
- Input sanitization
- Endpoint rate limiting
- Ephemeral room/DM identifiers
- Optional client-side cryptographic workflows

No system can guarantee perfect security. Users should treat anonymity and privacy as risk reduction, not absolute guarantees.

---

## 6. Legal and Abuse Handling

Privacy-focused operation does not authorize illegal activity. If abuse or unlawful behavior is detected, operators may take defensive actions consistent with applicable law and policy.

See:

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md)

---

## 7. Policy Changes

We may update this policy to reflect legal, security, or operational changes.

When updated:

- `Last Updated` and `Version` metadata will change
- Significant changes should be announced in repository documentation

---

## 8. Contact

**Hyperion Gray LLC**

- Website: https://www.hyperiongray.com
- Repository: https://github.com/HyperionGray/opsechat
- Security: see `SECURITY.md`

---

**Version:** 1.0 (Draft - Alpha Release)

---

*This document is a policy draft and should be reviewed by legal counsel before production launch.*
