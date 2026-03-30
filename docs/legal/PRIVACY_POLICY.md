# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** March 30, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Scope

This Privacy Policy explains what data opsechat may process, how long it is retained, and the controls we apply to protect user privacy.

This project is designed around ephemeral communication, in-memory processing, and minimal persistent metadata.

---

## 2. Core Privacy Principles

1. **In-memory first:** user content is handled in process memory and expires automatically.
2. **Minimal retention:** data is not retained longer than required for service operation.
3. **Security by default:** transport and browser protections are enabled where practical.
4. **Transparency:** legal and policy documents are published with source references.

---

## 3. Data We Process

### 3.1 Chat Data

- Chat messages and direct messages are processed in memory.
- Chat messages are designed to expire quickly (for example, short-lived room history).
- Direct messages are time-limited and removed after expiry.

### 3.2 Session Data

- Temporary session identifiers may be assigned by the server.
- Session metadata can include timing and rate-limit counters used for abuse prevention.

### 3.3 Operational Metadata

- Basic health, reliability, and abuse-prevention telemetry may be collected.
- Metadata is minimized and should avoid storing sensitive content.

---

## 4. Data We Do Not Intend to Collect

The service is designed to avoid unnecessary collection of:

- Long-term plaintext chat archives
- Persistent user profiles for anonymous chat usage
- Any data not required for core functionality, security, or legal compliance

---

## 5. Retention and Deletion

- Ephemeral chat and DM records are deleted automatically after their expiry window.
- In-memory structures are periodically cleaned up.
- Persistent legal and documentation files are stored in the repository for transparency and auditability.

---

## 6. Security Controls

The application uses multiple protections including:

- Security headers (CSP, frame protection, content-type protection, referrer policy)
- Input validation and sanitization for user-submitted content
- Endpoint rate limiting to reduce abuse and automated attacks

No security system is perfect, and users should apply their own operational security practices.

---

## 7. Legal Basis and Compliance

Use of the service is also governed by:

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md)

If required by applicable law, we may disclose data that is available to us in response to valid legal process.

---

## 8. User Rights

Depending on jurisdiction, users may have rights to access, correction, deletion, or objection regarding personal data.  
Because the service is largely ephemeral, retained data may be limited or unavailable by design.

---

## 9. International Use

Users are responsible for ensuring their usage complies with local laws in their jurisdiction, including privacy and communications laws.

---

## 10. Changes to this Policy

We may update this Privacy Policy as the product evolves. Material changes should be reflected by updating the "Last Updated" date and publishing the revised document.

---

## 11. Contact

For policy questions or privacy concerns, use project security/reporting channels documented in `SECURITY.md` and legal documentation.

---

*This is a draft policy and should receive legal review before production use.*
