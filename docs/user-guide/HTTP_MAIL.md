# HTTP Mail Guide

## Overview

HTTP Mail provides mailbox-style messaging over HTTP without SMTP/IMAP.

- Mailbox owners create an `address` and a secret `read_key`.
- Anyone with the address can send a message.
- Only users with the matching read key can read or delete messages.
- Messages expire automatically after 24 hours.
- Data is in-memory only.

## Endpoints

Base path: `/<path>/mail`

- `POST /<path>/mail/new` - create mailbox
- `POST /<path>/mail/<address>/send` - send message
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - read inbox
- `POST /<path>/mail/<address>/delete/<message_id>` - delete message
- `POST /<path>/mail/<address>/destroy` - destroy mailbox

## Security model

1. **Default deny for reads**: wrong or missing `read_key` returns access denied.
2. **Memory scrubbing**: message content is overwritten before deletion.
3. **No disk persistence**: storage is process memory only.
4. **Destroyed mailbox write guard**: once mailbox destruction starts, new writes are rejected.

### Destroyed mailbox write guard

During mailbox destruction, a concurrent sender can still hold a stale mailbox reference.
To prevent race-condition writes, mailbox state now uses a `destroyed` flag checked by
message writes. If a write reaches a destroyed mailbox, the send endpoint returns:

- `410 Gone` with JSON: `{"error": "Mailbox is no longer available"}`

This makes concurrent destroy/send behavior explicit and safe.
