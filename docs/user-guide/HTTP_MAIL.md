# HTTP Mail User Guide

## Overview

HTTP Mail is an inbox model that runs fully over HTTP without SMTP/IMAP dependencies.

- Mailbox owners create an address and private read key.
- Anyone with the address can send messages.
- Only users with the read key can read, delete, or destroy mailbox content.
- Data remains in memory only; no disk persistence.

## Endpoints

All endpoints are prefixed with `/<path>/mail`:

- `GET /<path>/mail` - HTTP Mail web UI
- `POST /<path>/mail/new` - create mailbox
- `POST /<path>/mail/<address>/send` - send message to mailbox
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - read inbox
- `POST /<path>/mail/<address>/rotate-key` - rotate mailbox read key
- `POST /<path>/mail/<address>/delete/<id>` - delete one message
- `POST /<path>/mail/<address>/destroy` - destroy mailbox

## Read Key Rotation

If a read key is suspected to be exposed, rotate it immediately:

1. Open inbox with the current read key.
2. Use **Rotate Read Key** in the danger zone.
3. Save the new key.
4. Stop using the old key (it is invalid immediately).

Rotation does not delete mailbox data; existing messages remain available with the new key.

## Message and Mailbox Lifecycle

- Messages expire after 24 hours.
- Message bodies are overwritten in memory before deletion.
- Empty mailboxes older than 48 hours are cleaned up opportunistically during normal route usage.

## Security Notes

- Share mailbox address broadly only as needed.
- Never share read keys in the same channel as sensitive message content.
- Use Tor/TLS transport where possible for additional network privacy.
