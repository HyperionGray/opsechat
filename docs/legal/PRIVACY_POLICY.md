# Privacy Policy

**Effective Date:** March 20, 2026  
**Last Updated:** March 20, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Scope

This Privacy Policy explains how opsechat handles data when you use:
- Web chat rooms
- TUI chat
- Email and burner email features
- Related operational endpoints (for example, health checks and abuse controls)

This document is a technical and legal draft for alpha. Legal review is still required before production launch.

---

## 2. Privacy Model

opsechat is designed with an in-memory, ephemeral architecture:
- Messages are stored in memory, not persisted to disk by default.
- Chat messages auto-expire and are overwritten in memory before deletion.
- Direct messages are short-lived and auto-expire.
- Service endpoints are designed for low metadata retention.

This architecture reduces retention but does not eliminate all risk.

---

## 3. Data We Process

### 3.1 Data You Provide
- Chat messages
- Direct messages
- Email content (if configured)
- Optional configuration values entered into the UI

### 3.2 Operational Metadata
- Randomized session identifiers
- Endpoint request timing
- Rate-limit counters
- Minimal health/service telemetry

### 3.3 Data We Intend Not to Persist
- Persistent chat history
- Long-term account profiles (current architecture is session-based)
- IP address level tracking as a product feature

---

## 4. How We Use Data

We process data to:
- Deliver chat and email features
- Apply abuse controls (rate limiting, validation, policy enforcement)
- Keep the service running (health and reliability checks)
- Investigate abuse and respond to legal obligations

We do not sell personal data.

---

## 5. Retention and Deletion

- Chat messages: short retention, auto-expiring (minutes).
- DM payloads: short retention, auto-expiring (about one minute).
- Session-level counters: retained only as needed for active protections.
- Operational logs: minimal and limited to operational needs.

Because data is ephemeral, historical recovery may be impossible by design.

---

## 6. Security Controls

Controls include:
- TLS in deployment configurations where supported
- Security headers for HTTP responses
- Input sanitization and validation
- Rate limiting on write-heavy endpoints
- In-memory overwriting for expired ephemeral messages

No system can guarantee absolute security.

---

## 7. Sharing and Disclosure

We may disclose information:
- To comply with legal process (for example, valid warrants/subpoenas)
- To investigate abuse or protect users and infrastructure
- To vendors or infrastructure providers strictly for service operations

Where legally allowed, we prefer transparency about these disclosures.

---

## 8. International Use

Users are responsible for complying with local law. Data may be processed in jurisdictions where infrastructure is hosted.

---

## 9. Your Choices

You can reduce exposure by:
- Limiting what you share in messages
- Using Tor and secure endpoint practices
- Avoiding sensitive identifiers in chat/email content
- Rotating sessions and burner addresses appropriately

Given ephemeral design, data export and historical retrieval may be limited.

---

## 10. Children

The service is intended for adults. If you believe a minor has provided personal information, contact the project maintainers to request deletion where possible.

---

## 11. Policy Changes

We may update this policy as features and legal requirements evolve. Material changes should include an updated date and revision note.

---

## 12. Contact

- Repository: https://github.com/HyperionGray/opsechat
- Company: Hyperion Gray LLC
- Security contact: See SECURITY.md

---

*Draft for alpha release. Legal counsel review required before production.*
