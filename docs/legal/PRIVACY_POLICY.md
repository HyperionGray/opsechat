# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** April 4, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Purpose

This Privacy Policy explains how opsechat handles information when you use the service. opsechat is designed for privacy-preserving communication with strong defaults: short-lived in-memory data, no persistent message logs, and client-side encryption support.

By using the service, you acknowledge this policy together with our [Terms of Service](TERMS_OF_SERVICE.md) and [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md).

---

## 2. Core Privacy Design

opsechat is built around the following principles:

- In-memory communication with automatic expiry
- Minimal metadata collection
- No plaintext decryption capability by default
- No routine long-term retention of chat content
- Transport through privacy-preserving network paths where configured

These are engineering goals, not absolute guarantees. See "Security and Limitations" below.

---

## 3. Information We Process

### 3.1 Message Content

- Chat and direct-message content is held in process memory for a short window
- Messages are designed to expire automatically
- Expired message buffers are overwritten before removal where implemented
- We do not intentionally persist chat content to disk as part of normal operation

### 3.2 Session Information

To make the application function, temporary session-related values are processed:

- Random session identifiers
- Temporary usernames and display color metadata
- Basic timing information needed for expiry and abuse controls

### 3.3 Operational and Security Data

We may process limited technical data required to run and secure the system:

- Request timing and endpoint usage
- Rate-limit counters
- Health and error diagnostics
- Minimal service telemetry

We configure these controls to support reliability and abuse prevention rather than profiling.

---

## 4. Information We Do Not Intend to Collect

By default architecture, we do not aim to keep:

- Persistent plaintext chat archives
- Long-term user profiles tied to real-world identity
- Behavioral advertising identifiers

Where infrastructure or host environment tools generate standard operational logs outside the app, those are controlled by deployment operators.

---

## 5. Encryption and Key Handling

- Some communication modes support end-to-end encryption
- Encryption keys are generated and handled client-side in supported workflows
- Server components are not designed to recover your private keys
- If keys are lost, recovery may be impossible

Encryption protects message content, but does not hide all metadata (for example, timing and message size patterns).

---

## 6. Data Retention

Retention is intentionally short where possible:

- Chat messages: ephemeral, auto-expiring by design
- Direct messages: short-lived with automatic expiry
- Session/rate-limit state: temporary and periodically cleaned
- Diagnostics: minimal and environment-dependent

Exact retention behavior can vary by deployment topology and host configuration.

---

## 7. Cookies and Local Storage

The service may use session cookies and browser storage required for security and functionality (for example, local cryptographic key storage in supported client features).

We do not use these mechanisms for third-party ad tracking.

---

## 8. Third-Party Services

Depending on deployment and feature usage, integrations may involve third-party services (for example infrastructure providers, optional security tooling, or email backends). Each third party has its own privacy and retention practices.

Operators should review and configure these systems before production use.

---

## 9. Legal Basis and Compliance Intent

Where applicable laws require a legal basis, processing is generally performed for:

- Service operation
- Security and abuse prevention
- Compliance with legal obligations
- Legitimate interests in maintaining system integrity

This project is under active development. Additional jurisdiction-specific disclosures may be required before production launch.

---

## 10. Law Enforcement and Legal Requests

When legally required, we may disclose information available to us in response to valid legal process.

Because the platform is designed for ephemeral handling and limited retention, available data may be minimal. We do not promise to notify users of legal requests when prohibited by law.

---

## 11. International Use

The service may be accessed from multiple jurisdictions. Data handling may occur wherever infrastructure is operated. Users are responsible for understanding local legal requirements.

---

## 12. User Rights

Depending on jurisdiction, you may have rights such as:

- Access requests
- Correction requests
- Deletion requests
- Restriction or objection requests
- Portability requests

Given the system's ephemeral design, data may no longer be available at request time. Where data exists and rights apply, we will process requests consistent with legal obligations.

---

## 13. Security and Limitations

We implement reasonable security controls, including strict headers, input sanitization, and abuse controls. However:

- No system is perfectly secure
- Anonymity systems have limits
- Endpoint/device compromise can bypass transport protections
- Implementation defects may exist

Use the service only if you understand and accept these risks.

---

## 14. Children's Privacy

The service is not intended for children. If applicable law requires a specific age threshold, users must meet that threshold to use the service.

---

## 15. Changes to This Policy

We may update this policy as the product evolves. Material changes will be published through normal project documentation channels.

Continued use after updates constitutes acceptance where legally permitted.

---

## 16. Contact

For privacy and security-related questions, use project contact channels documented in repository policy files.

---

## 17. Status Notice

This policy is a production-oriented draft and still requires formal legal review before broad production use.
