# Privacy Policy

**Effective Date:** [To Be Determined]  
**Last Updated:** April 5, 2026  
**Service:** opsechat  
**Provider:** Hyperion Gray LLC

---

## 1. Purpose

This Privacy Policy explains what information opsechat may process, how long it is retained, and your responsibilities when using a privacy-focused communication service.

---

## 2. Core Privacy Model

- In-memory-first architecture (no intentional persistent chat/email storage by default)
- Ephemeral sessions and expiring message lifetimes
- Tor-based access model where applicable
- Client-side encryption features for supported message flows

---

## 3. Information We Process

### 3.1 Data you provide directly
- Message content you submit during active sessions
- Optional email metadata and message content in enabled mail features
- User-supplied keys or encrypted payloads in supported flows

### 3.2 Operational metadata
- Session identifiers and timestamps
- Service health and uptime telemetry
- Abuse prevention and rate-limit signals

### 3.3 Data we do not intentionally collect
- Traditional long-term account profiles (unless introduced in future versions)
- Persistent plaintext message history as a product feature

---

## 4. Retention

- Chat and direct-message data is designed to expire quickly by feature policy.
- Some operational metadata may exist transiently for abuse controls and reliability.
- If logs are produced for troubleshooting, they should be minimal and short-lived.

Because this is an alpha system, retention guarantees may evolve as controls are hardened and legally reviewed.

---

## 5. Legal and Abuse Handling

We may process and disclose data that is available to us when required to:

- comply with valid legal process;
- investigate abuse, fraud, or threats to safety;
- enforce the Terms of Service and Acceptable Use Policy.

For prohibited activity standards, see [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md).  
For service terms, see [Terms of Service](TERMS_OF_SERVICE.md).

---

## 6. Security Practices

- Security headers and input validation are applied at the web layer.
- Encryption support is available for relevant flows; key custody remains user responsibility.
- We continue to harden protections during alpha, including abuse prevention and testing coverage.

No system can provide perfect security; use the service with informed caution.

---

## 7. International Use

Users are responsible for complying with laws in their jurisdiction. Data handling obligations may vary by location and legal regime.

---

## 8. Your Responsibilities

You are responsible for:

- maintaining control of your devices and credentials;
- safeguarding keys and passphrases;
- understanding that expired/ephemeral data may not be recoverable;
- using the service lawfully.

---

## 9. Policy Changes

We may revise this policy as the platform matures. Updated versions will be published in the repository and associated documentation.

---

## 10. Contact

**Hyperion Gray LLC**

- Website: https://www.hyperiongray.com
- Repository: https://github.com/HyperionGray/opsechat
- Security issues: see SECURITY.md
- Abuse reports: see [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md)

---

*Draft policy for alpha. Legal review is required before production launch.*
