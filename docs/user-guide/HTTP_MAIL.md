# HTTP Mail Guide

## Overview

HTTP Mail is a mailbox feature that works entirely over HTTP, with no SMTP or IMAP requirements.
Each mailbox has:

- A public **address** (share with senders)
- A private **read key** (required to read inbox contents)

The system is default-deny: without the read key, inbox reads fail.

## Security Model

- Anyone with mailbox address can send messages
- Only the read key holder can read or delete messages
- Messages auto-expire after 24 hours
- Deleted and expired messages are overwritten in memory before removal
- Mailbox destruction scrubs all messages and rejects stale writes
- Read keys can be rotated to invalidate old access

## Routes

Assuming `/{path}` is your random server path:

- `GET /{path}/mail` - HTTP Mail UI
- `POST /{path}/mail/new` - create mailbox
- `POST /{path}/mail/send` - send message (form/no-JS fallback; address in form)
- `POST /{path}/mail/{address}/send` - send message (address in path)
- `GET /{path}/mail/{address}/inbox?key=<read_key>` - read inbox
- `POST /{path}/mail/{address}/delete/{msg_id}` - delete message
- `POST /{path}/mail/{address}/rotate-key` - rotate read key
- `POST /{path}/mail/{address}/destroy` - destroy mailbox

## No-JavaScript Usage

1. Open `/{path}/mail`
2. Create a mailbox and save:
   - address
   - read key
3. Send a message:
   - Use "Send a Message"
   - Enter recipient mailbox address
   - Submit form (uses `/mail/send` fallback route)
4. Read inbox:
   - Enter address + read key
   - Open inbox
5. Optional key rotation:
   - In inbox section, rotate key to invalidate previous key
   - Save new key immediately

## JSON API Examples

Create mailbox:

```bash
curl -s -X POST "http://127.0.0.1:5001/<path>/mail/new"
```

Send message:

```bash
curl -s -X POST "http://127.0.0.1:5001/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test","sender":"alice"}'
```

Read inbox:

```bash
curl -s "http://127.0.0.1:5001/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```

Rotate read key:

```bash
curl -s -X POST "http://127.0.0.1:5001/<path>/mail/<address>/rotate-key" \
  -H "Content-Type: application/json" \
  -d '{"read_key":"<read_key>"}'
```

Destroy mailbox:

```bash
curl -s -X POST "http://127.0.0.1:5001/<path>/mail/<address>/destroy" \
  -H "Content-Type: application/json" \
  -d '{"read_key":"<read_key>"}'
```
