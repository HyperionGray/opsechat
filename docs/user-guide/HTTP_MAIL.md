# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over plain HTTP without SMTP/IMAP.

## Overview

Each mailbox has:

- **Address** (public): safe to share with senders.
- **Read key** (private): required to read, delete, or destroy mailbox contents.

Security model:

- Default deny for inbox reads.
- In-memory storage only (no disk persistence).
- Message content is overwritten in memory before deletion.

## Quick Start

1. Open `/<path>/mail`.
2. Create a new mailbox.
3. Save the returned address and read key.
4. Share the address with senders.
5. Read inbox using the address + read key.

## Compose Behavior

You can send mail in two ways:

- `POST /<path>/mail/<address>/send` (direct address route)
- `POST /<path>/mail/send` (address provided in request body/form)

The second endpoint is useful for non-JavaScript clients and HTML form fallback.

## Limits and Retention

- Max message body length: `2000` characters.
- Message retention: `24` hours.
- Per-mailbox live message cap: `200` messages (after expiry cleanup).

When a mailbox is full, send requests return HTTP `429`.

## API Summary

- `GET /<path>/mail` - HTTP Mail UI
- `POST /<path>/mail/new` - create mailbox
- `POST /<path>/mail/send` - send using address from form/JSON
- `POST /<path>/mail/<address>/send` - send directly to address
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - read messages
- `POST /<path>/mail/<address>/delete/<msg_id>` - delete one message
- `POST /<path>/mail/<address>/destroy` - destroy mailbox

## Notes

- Destroying a mailbox removes it from global lookup and blocks future writes.
- If a sender receives "mailbox not found", the owner likely destroyed or rotated it.
