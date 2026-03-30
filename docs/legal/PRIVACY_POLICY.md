# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** March 30, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Overview

This Privacy Policy explains how opsechat handles information when you use the service. opsechat is designed around ephemeral, in-memory communication. We aim to minimize data collection and retention by default.

This policy complements our [Terms of Service](TERMS_OF_SERVICE.md) and [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md).

---

## 2. Privacy by Design

opsechat is built with the following design goals:

- In-memory operation where practical
- Short-lived message retention
- Client-side encryption support
- Minimal metadata collection
- No advertising-based profiling

These controls reduce available data, but they do not make users immune from legal process, endpoint compromise, or broader network-level risks.

---

## 3. Information We Process

Depending on how the service is used, opsechat may process:

- Temporary session identifiers
- Message content stored in memory during active use
- Message metadata (timing, room/session association)
- Service health and operational telemetry
- Configuration data required to provide enabled features

We do not claim perfect anonymity and cannot guarantee that every environment running opsechat has identical logging behavior.

---

## 4. Information We Intend Not to Retain

The service is designed to avoid long-term retention of:

- Persistent chat transcripts
- Long-term user profiles
- Unnecessary identifying metadata

Messages in simple chat rooms are configured to expire automatically. Some other data may still exist temporarily in process memory, transient logs, or infrastructure-level systems.

---

## 5. Encryption and Keys

- Some features support client-side encryption.
- When encryption is handled entirely client-side, providers cannot decrypt message content without access to user key material.
- You are responsible for key handling, backup, and endpoint security.

Losing keys or using compromised endpoints can result in permanent data loss or data exposure.

---

## 6. Cookies, Sessions, and Similar Mechanisms

opsechat uses session mechanisms to provide core functionality such as room participation, temporary identity state, and abuse controls.

These mechanisms may include:

- Session cookies
- In-memory session state
- Rate-limiting identifiers

Session data is operationally necessary and may expire automatically.

---

## 7. Operational Logging

Operators may maintain limited logs for:

- Reliability and uptime
- Abuse prevention
- Security monitoring
- Incident response

Log scope and retention may vary by deployment. Self-hosted operators are responsible for configuring their own logging and retention policies.

---

## 8. Legal Bases and Law Enforcement Requests

Where applicable law requires a legal basis, processing is generally tied to:

- Providing requested service functionality
- Security and abuse prevention
- Compliance with legal obligations
- Legitimate operational interests

If we receive valid legal process, we may disclose data that is available and required by law. Architectural limits may reduce what data exists at request time.

---

## 9. Data Retention

Retention depends on feature and deployment context:

- Ephemeral chat messages: short-lived by design
- Session and abuse-control state: retained only as needed for operation
- Operational logs: limited retention based on deployment policy

No retention policy can guarantee immediate deletion from all memory, caches, or backups in every environment.

---

## 10. International Use

opsechat may be accessed from multiple jurisdictions. Legal requirements vary, and users are responsible for understanding their local obligations. Operators should review region-specific privacy and security requirements before production use.

---

## 11. Your Choices

Depending on deployment and feature set, users may be able to:

- Limit personally identifying content shared in messages
- Rotate temporary identities and rooms
- Use client-side encryption features
- Stop using the service at any time

Because the service is designed for minimal persistence, account-style export and deletion workflows may differ from conventional platforms.

---

## 12. Security Practices

We apply practical controls such as:

- Input validation and sanitization
- Security headers
- Rate-limiting and abuse controls
- Dependency and code review workflows

No system is risk-free. Users should treat endpoint security and operational discipline as essential.

---

## 13. Children’s Privacy

opsechat is intended for adults and is not designed for use by children. If an operator becomes aware of unlawful collection involving minors, appropriate remediation steps should be taken in accordance with applicable law.

---

## 14. Policy Updates

We may revise this Privacy Policy as the service evolves. Updated versions will include a revised “Last Updated” date and may become effective immediately when required for legal or security reasons.

---

## 15. Contact

**Hyperion Gray LLC**

- Website: https://www.hyperiongray.com
- Repository: https://github.com/HyperionGray/opsechat
- Security and abuse channels: see project documentation

---

## 16. Draft Status

This document is a working policy draft for current project state and still requires legal review before production launch.

**Checklist before production use:**

- [ ] Legal counsel review and approval
- [ ] Jurisdiction-specific compliance review
- [ ] Finalize contact channels
- [ ] Confirm deployment-specific retention settings
- [ ] Integrate policy acceptance in user onboarding
