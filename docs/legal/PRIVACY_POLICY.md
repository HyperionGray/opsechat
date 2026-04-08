# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** April 8, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Overview

This Privacy Policy explains how opsechat handles information when you use the service.  
opsechat is designed around ephemeral, in-memory communication and privacy-preserving defaults.

Because architecture choices directly affect data handling, this policy describes both:

- what we intentionally do not collect or retain, and
- what minimal technical metadata may exist during active use.

---

## 2. Core Privacy Design

The service is built with the following principles:

- **In-memory operation:** chat and temporary message content are stored in process memory.
- **Ephemeral retention:** messages automatically expire.
- **Client-side encryption support:** encrypted room content can be generated in the browser.
- **No persistent chat archive by default:** expired content is not kept for historical retrieval.
- **Tor-oriented access model:** deployment patterns are intended to reduce source attribution.

These are engineering constraints, not absolute legal or security guarantees.

---

## 3. Information We Process

### 3.1 Data You Provide During Use

Depending on features used, the service may process:

- chat messages,
- temporary direct messages for room sharing,
- session identifiers,
- optional email-related content if those modules are enabled by operators.

### 3.2 Automatically Generated Operational Data

During runtime, the service may create:

- transient session values,
- request timing metadata,
- minimal service health telemetry (for uptime/monitoring),
- rate-limiting counters needed to defend against abuse.

---

## 4. Data We Intentionally Minimize

By design, opsechat aims to avoid persistent collection of:

- long-lived user profiles,
- durable chat history,
- message archives for retrospective browsing.

Where feasible, this project favors volatile storage and short retention windows.

---

## 5. Message Retention and Expiry

Current default behavior includes:

- chat message expiry (short-lived),
- temporary DM expiry (short-lived),
- memory-overwrite behavior before deletion for selected fields.

Retention values are implementation details and may change with future releases.  
Operators deploying customized builds are responsible for disclosing their own retention settings.

---

## 6. Security Controls

The project uses multiple controls intended to reduce risk, such as:

- strict HTTP security headers,
- request rate limiting for abuse prevention,
- input sanitization and bounded payload limits,
- dependency and code review workflows.

No software can guarantee perfect confidentiality or anonymity.  
Users should assume realistic threat models and operational limitations.

---

## 7. Law Enforcement and Legal Requests

If legally compelled through valid process, operators may be required to provide data that is technically available at the time of request.

Due to ephemeral architecture:

- some data may not exist anymore at request time,
- encrypted content may not be decryptable by operators,
- available metadata may be limited.

Nothing in this policy prevents lawful cooperation where required.

---

## 8. International Use

Users are responsible for ensuring their use complies with laws in their jurisdiction.

If this service is operated in or accessed from multiple regions, applicable privacy obligations may vary.  
This policy is a project baseline and may require operator-specific addenda.

---

## 9. Your Responsibilities

You are responsible for:

- securing your own endpoint/device,
- managing your encryption keys and backups,
- understanding that key loss may be unrecoverable,
- using the service lawfully and in line with the AUP and Terms.

---

## 10. Changes to This Policy

This policy may be updated as features, retention behavior, or legal requirements evolve.

When changes are made, the "Last Updated" date will be revised.  
Material changes should be communicated through repository documentation updates.

---

## 11. Related Policies

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md)
- [Security Guidance](../../SECURITY.md)

---

## 12. Contact

For privacy or legal questions, use the project channels documented in the repository until dedicated contact points are finalized.

---

*This policy is a technical baseline for an alpha-stage project and should receive formal legal review before production launch.*
