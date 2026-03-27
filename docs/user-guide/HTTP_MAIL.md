# HTTP Mail Guide

## Overview

HTTP Mail provides a minimal mailbox system that runs entirely over HTTP:

- No SMTP setup
- No IMAP setup
- In-memory storage only
- Default-deny inbox access using a private read key

This feature is useful when you want quick message drops inside the existing opsechat session without configuring external mail infrastructure.

Access URL:

`/{path}/mail`

## Security Model

Each mailbox has:

- **Address** (public): safe to share with senders
- **Read Key** (private): required to read inbox and manage mailbox

Without the read key, inbox reads are denied.

### Data Lifecycle

- Messages are stored in memory only
- Messages auto-expire after 24 hours
- Deletions overwrite message content in memory before removal
- Destroying a mailbox removes it from global lookup and scrubs stored messages

## Core Flows

### 1) Create mailbox

Creates a mailbox and returns:

- `address`
- `read_key`
- `send_url`
- `inbox_url`

Endpoint:

`POST /{path}/mail/new`

### 2) Send message

Senders only need mailbox address.

Endpoint:

`POST /{path}/mail/{address}/send`

No-JS fallback endpoint is also available:

`POST /{path}/mail/send` with form field `_address_override`

### 3) Read inbox

Inbox requires read key.

Endpoint:

`GET /{path}/mail/{address}/inbox?key={read_key}`

### 4) Rotate read key

Mailbox owner can rotate the read key (old key becomes invalid immediately).

Endpoint:

`POST /{path}/mail/{address}/rotate-key`

Body:

- JSON: `{ "read_key": "current_key" }`
- or form field: `read_key=current_key`

### 5) Delete message

Endpoint:

`POST /{path}/mail/{address}/delete/{message_id}`

### 6) Destroy mailbox

Endpoint:

`POST /{path}/mail/{address}/destroy`

Once destroyed, writes are refused and the mailbox is no longer resolvable by address.

## API Notes

- JSON clients should send `Accept: application/json`
- Errors are explicit:
  - `404` mailbox not found
  - `403` invalid read key
  - `410` mailbox is no longer available for writes

## Operational Tips

- Treat read keys as secrets; avoid sharing in logs/screenshots
- Rotate read keys after suspected exposure
- For longer-lived or external delivery workflows, use the full SMTP/IMAP email system instead
