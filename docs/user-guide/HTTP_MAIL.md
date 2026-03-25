# HTTP Mail (Email-over-HTTP) Guide

## Overview

HTTP Mail provides mailbox-style messaging over plain HTTP endpoints without SMTP or IMAP.
Each mailbox has:

- a public **address** (safe to share with senders)
- a private **read key** (required to read/delete/destroy mailbox data)

Design goals:

- default-deny mailbox reads
- in-memory-only storage
- automatic message expiry
- explicit memory overwrite on deletion/destroy
- no JavaScript dependency for core send/read workflows

## Endpoints

All routes are under:

`/<path>/mail`

### Core

- `GET /<path>/mail`
  - HTTP Mail page (create mailbox, compose, read inbox)
- `POST /<path>/mail/new`
  - create mailbox
  - returns JSON with `address`, `read_key`, `send_url`, `inbox_url`
- `POST /<path>/mail/send`
  - non-JavaScript compose fallback
  - requires form field `_address_override`
- `POST /<path>/mail/<address>/send`
  - send message to a mailbox by address (JSON or form)
- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - read mailbox (requires valid key)
- `GET /<path>/mail/<address>/stats?key=<read_key>`
  - mailbox metadata (requires valid key)
- `POST /<path>/mail/<address>/delete/<msg_id>`
  - delete one message (requires `read_key`)
- `POST /<path>/mail/<address>/destroy`
  - destroy mailbox and scrub contents (requires `read_key`)

## Mailbox lifecycle hardening

The mailbox implementation includes lifecycle protections:

1. **Destroy flag**  
   A mailbox has a `destroyed` state. Once destroyed, all reads/writes are denied.

2. **Secure destroy**  
   Destroy operation overwrites:
   - every stored message body/subject/sender
   - mailbox `read_key`
   - mailbox `address`
   Then marks mailbox destroyed.

3. **Concurrent-safety behavior**  
   Writers (`add_message`) check the mailbox lifecycle state under lock and reject writes to destroyed mailboxes.

4. **Cleanup hardening**  
   stale mailbox cleanup uses secure destroy for removed mailboxes.

## Mailbox stats response

`GET /<path>/mail/<address>/stats?key=<read_key>`

returns:

```json
{
  "address": "aBcDeFgHiJkL",
  "created_at": "2026-03-25T20:00:00.000000",
  "age_seconds": 1234,
  "message_count": 2,
  "latest_message_at": "2026-03-25T20:15:00.000000"
}
```

## Non-JavaScript compose flow

The compose form posts to:

`POST /<path>/mail/send`

with:

- `_address_override` (recipient mailbox address)
- `sender`
- `subject`
- `body`

This route supports a full send path when JavaScript is disabled.

## Security notes

- Without the read key, mailbox reads are denied.
- Messages are automatically expired after the configured window.
- Deleted/destroyed content is overwritten in memory before removal.
- Data remains in memory only; no mailbox persistence layer is used.

