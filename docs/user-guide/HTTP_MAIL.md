# HTTP Mail User Guide

## Overview

HTTP Mail is a lightweight mailbox system that runs entirely over HTTP (no SMTP/IMAP).
Each mailbox has:

- **Address**: safe to share with senders
- **Read key**: private secret required to read, delete, rotate key, or destroy mailbox

Messages are stored in memory only and expire automatically.

## Endpoints

Base path: `/{path}/mail`

- `GET /{path}/mail` - HTML UI
- `POST /{path}/mail/new` - create mailbox
- `POST /{path}/mail/send` - no-JS compose fallback (form includes recipient address)
- `POST /{path}/mail/{address}/send` - send to known mailbox address
- `GET /{path}/mail/{address}/inbox?key={read_key}` - read inbox
- `POST /{path}/mail/{address}/delete/{msg_id}` - delete one message
- `POST /{path}/mail/{address}/rotate-key` - rotate read key
- `POST /{path}/mail/{address}/destroy` - destroy mailbox

## Read Key Rotation

If a read key might be exposed, rotate it immediately:

1. Open the mailbox inbox section.
2. Use **Rotate Read Key**.
3. Save the returned replacement key.
4. The old key stops working right away.

This reduces blast radius if a link, screenshot, or clipboard leak occurred.

## Security Behavior

- Default deny: inbox reads require exact key match
- Destroyed mailboxes reject concurrent in-flight sends
- Expired/deleted messages are overwritten before removal
- No disk persistence for mailbox data

## No-JavaScript Compatibility

Sending now works without JavaScript via `POST /{path}/mail/send`.
The form includes `_address_override` so users in strict NoScript setups can still compose and deliver messages.

