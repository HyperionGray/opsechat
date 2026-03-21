# HTTP Mail User Guide

## Overview

HTTP Mail is a lightweight mailbox system that runs entirely over HTTP.
It does not require SMTP or IMAP and keeps messages in memory only.

Core model:
- Public mailbox address: share with senders
- Private read key: required to read/delete/destroy mailbox
- Default-deny reads: wrong or missing key returns access denied
- Auto-expiry: messages expire after 24 hours

## Endpoints

All routes are under:

`/{path}/mail`

Primary operations:

- `GET /{path}/mail`
  - HTTP Mail UI
- `POST /{path}/mail/new`
  - Create mailbox; returns `address` + `read_key`
- `POST /{path}/mail/{address}/send`
  - Send message directly to known mailbox address
- `POST /{path}/mail/send`
  - No-JavaScript compose fallback (address in request body/form)
- `GET /{path}/mail/{address}/inbox?key=<read_key>`
  - Read inbox (requires valid read key)
- `POST /{path}/mail/{address}/delete/{msg_id}`
  - Delete one message (requires read key)
- `POST /{path}/mail/{address}/destroy`
  - Destroy mailbox and securely wipe in-memory message content

## JavaScript and No-JavaScript Operation

The UI supports both modes:

- JavaScript mode dynamically targets `/{path}/mail/{address}/send`.
- No-JavaScript mode posts to `/{path}/mail/send` and includes the
  recipient address in form data.

This ensures compose/send works even when scripting is unavailable.

## Message Rules

- Body is required.
- Subject defaults to `(no subject)` when empty.
- Sender defaults to `anonymous` when empty.
- Input is sanitized to plain text.
- Maximum message length: `2000` characters.

## Security Notes

- Read access uses constant-time key comparison.
- Mailbox deletion overwrites message fields before removing data.
- Destroyed mailboxes reject new message writes.
- Content Security Policy (CSP) uses per-request nonces for inline template
  script/style blocks without enabling global `unsafe-inline`.

## API Example

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/{path}/mail/new"
```

Send message:

```bash
curl -s -X POST "http://localhost:5000/{path}/mail/send" \
  -H "Content-Type: application/json" \
  -d '{"address":"<mailbox-address>","subject":"Hi","body":"Hello","sender":"alice"}'
```

Read inbox:

```bash
curl -s "http://localhost:5000/{path}/mail/<mailbox-address>/inbox?key=<read-key>" \
  -H "Accept: application/json"
```

