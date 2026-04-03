# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** April 3, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Overview

This Privacy Policy explains how opsechat ("Service") handles data. opsechat is designed to minimize retained data by default and operate with an in-memory-first architecture.

By using the Service, you acknowledge this policy.

---

## 2. Core Privacy Model

### 2.1 In-Memory by Default
- Chat messages are stored in memory only.
- Data is automatically removed on expiration or restart.
- The service is designed to avoid persistent chat history.

### 2.2 Ephemeral Communication
- Chat messages are short-lived and expire automatically.
- Direct-message share links are temporary and short-lived.
- Rooms are cleaned up after inactivity.

### 2.3 Encryption Model
- Some features support client-side encryption.
- We are not able to decrypt user-controlled encrypted payloads.
- You are responsible for your key management.

---

## 3. Data We May Process

Depending on feature usage, we may process:

- Temporary session identifiers
- Message metadata (timing/size counters)
- Operational metrics (health and uptime data)
- Minimal technical logs needed for reliability

We do not intentionally maintain long-term plaintext message archives.

---

## 4. Data We Do Not Intend to Collect

The system is designed to avoid collecting or retaining:

- Persistent profile history for anonymous chat sessions
- Long-term message archives
- Unnecessary personal identifiers

Some metadata may still exist transiently in memory while a session is active.

---

## 5. Retention and Deletion

- Chat content is deleted automatically based on expiry windows.
- Temporary identifiers are removed as sessions and rate-limit windows age out.
- In-memory structures are purged by cleanup jobs and process restarts.

No deletion workflow can recover already-expired ephemeral content.

---

## 6. Security Measures

We apply baseline controls including:

- Security response headers (CSP, frame restrictions, MIME sniffing protection)
- Input validation and sanitization for user-submitted content
- Rate limiting on high-risk write endpoints
- Operational monitoring for service health

No software system can guarantee perfect security.

---

## 7. Legal Process and Compliance

If required by valid legal process, we may disclose data that is technically available at the time of the request. Because of ephemeral retention, available data may be limited.

For abuse and misuse boundaries, see the Acceptable Use Policy.

---

## 8. Your Responsibilities

You are responsible for:

- Protecting your own endpoint/device security
- Managing your encryption keys
- Sharing room links only with intended participants
- Complying with applicable laws

---

## 9. Policy Changes

We may update this policy as the service evolves. Material changes will be reflected with an updated "Last Updated" date.

---

## 10. Contact

**Hyperion Gray LLC**

- Website: https://www.hyperiongray.com
- Repository: https://github.com/HyperionGray/opsechat
- Security process: see SECURITY.md

---

*Draft policy for alpha-stage service evolution. Legal review is required before production commitments.*
