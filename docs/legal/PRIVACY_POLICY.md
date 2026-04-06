# Privacy Policy

**Effective Date:** April 6, 2026  
**Last Updated:** April 6, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Scope

This Privacy Policy explains how opsechat processes data when you use the service, including chat, burner email, and related policy pages.

Our design goal is to minimize retained data and avoid persistent storage whenever possible.

---

## 2. Privacy Principles

- Data minimization by default
- In-memory processing where feasible
- Short retention windows for ephemeral features
- Clear separation between policy/legal documents and application data

---

## 3. Data We Process

### 3.1 Session and operational metadata

We may process:

- Temporary session identifiers
- Request timing and rate-limit counters
- Service health metrics (uptime, active rooms)

### 3.2 Message and email data

- Chat messages are processed in memory
- Direct messages are processed in memory with short expiry
- Burner email metadata/content may be processed according to feature configuration

### 3.3 Data we do not intentionally collect as persistent records

- Long-term chat transcripts
- Persistent user profile records (in the current architecture)
- Permanent message archives in application storage

---

## 4. Retention

Retention is intentionally limited by feature design:

- Ephemeral chat and DM features use short memory windows
- In-memory structures are periodically cleaned up
- Some operational logs may exist for debugging and security maintenance

---

## 5. Security Practices

We apply layered controls, including:

- Input validation and sanitization
- Security headers
- Rate limiting on write-heavy endpoints
- Restricted content model for sensitive communication paths

No system can guarantee perfect anonymity or absolute security.

---

## 6. Legal Requests and Enforcement

If required by applicable law and valid legal process, we may disclose data that is technically available to us at the time of the request.

Because of ephemeral design choices, data availability may be limited.

---

## 7. Third-Party Components

The service may rely on external infrastructure and software components (for example, Tor network infrastructure, hosting providers, or registrar-related systems).

Those systems are governed by their own privacy and security policies.

---

## 8. Your Responsibilities

Users are responsible for:

- Protecting their own devices and browser environment
- Managing key material and secrets safely
- Understanding legal obligations in their jurisdiction

---

## 9. Policy Changes

We may update this policy to reflect legal, security, or product changes.

When updated, the **Last Updated** date changes and the latest version is published in the repository and policy routes.

---

## 10. Contact

For privacy-related questions, open an appropriate repository issue or use official project contact channels documented in repository policy documents.

---

**Version:** 1.0 (Draft - Alpha)  
**Status:** Requires legal review before production launch
