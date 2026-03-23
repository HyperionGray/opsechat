# HTTP Mail (Email over HTTP)

## Overview

HTTP Mail provides mailbox-style messaging without SMTP or IMAP dependencies.
Each mailbox has:

- `address` (public identifier used by senders)
- `read_key` (private secret required to read/delete/destroy)

Messages are stored in memory only and expire automatically.

## Security Model

- Default deny: inbox reads require the correct `read_key`
- Message data is overwritten in memory before deletion
- Destroying a mailbox scrubs all messages and permanently disables writes
- Mailbox identifiers use high-entropy URL-safe tokens

## Endpoints

Assuming `<path>` is your configured secret path:

- `GET /<path>/mail` - UI entry point
- `POST /<path>/mail/new` - create mailbox
- `POST /<path>/mail/<address>/send` - send message
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - read inbox
- `POST /<path>/mail/<address>/delete/<msg_id>` - delete message
- `POST /<path>/mail/<address>/destroy` - destroy mailbox

## Mailbox Destruction Semantics

Mailbox destruction is race-safe:

1. Mailbox is removed from global lookup.
2. Existing message bodies are overwritten in memory.
3. Mailbox is marked destroyed and rejects stale-reference writes.

If a send request races with mailbox destruction, send returns:

- `410 Gone` with `{"error": "Mailbox has been destroyed"}` (JSON mode)

## Example Flow (JSON)

1. Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

2. Send message:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test","sender":"alice"}'
```

3. Read inbox:

```bash
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```
