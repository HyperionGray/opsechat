# HTTP Mail User Guide

HTTP Mail provides inbox-style messaging over HTTP with no SMTP/IMAP dependency.
It is designed for short-lived, plain-text communication and keeps data in memory only.

## Security model

- Each mailbox has:
  - **address**: public identifier you share with senders
  - **read key**: private secret required to read/delete/destroy mailbox data
- Read operations are **default deny** without the correct read key.
- Messages expire after 24 hours.
- Destroyed mailboxes reject all new writes.

## Endpoints

Routes are scoped under `/<path>/mail`.

- `GET /<path>/mail` - HTTP Mail UI
- `POST /<path>/mail/new` - create mailbox
- `POST /<path>/mail/send` - send message from non-JS form (`_address_override`)
- `POST /<path>/mail/<address>/send` - send message directly to an address
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - read inbox
- `POST /<path>/mail/<address>/delete/<msg_id>` - delete one message
- `POST /<path>/mail/<address>/destroy` - destroy entire mailbox

## Quick start

1. Open `/<path>/mail`.
2. Create a mailbox and save the returned **address** and **read key**.
3. Share only the **address** with message senders.
4. To read, enter address + read key in the "Read My Inbox" section.

## Non-JavaScript sending

The compose form now posts to `/<path>/mail/send`, which supports server-side
address resolution via `_address_override`. This keeps compose functional even
when JavaScript is disabled.

## API examples

Create mailbox:

```bash
curl -X POST "http://localhost:5001/<path>/mail/new"
```

Send message:

```bash
curl -X POST "http://localhost:5001/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"anon"}'
```

Read inbox:

```bash
curl "http://localhost:5001/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```
