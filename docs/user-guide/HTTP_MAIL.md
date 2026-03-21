# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over plain HTTP, without SMTP/IMAP setup.

It is designed for quick, low-friction message drops:

- public mailbox address for senders
- private read key for inbox access
- in-memory only storage
- automatic message expiry (24 hours)

## Security Model

1. Create a mailbox to receive:
   - `address` (shareable)
   - `read_key` (secret)
2. Senders only need the address.
3. Readers must provide the read key.
4. If the read key is wrong, inbox reads are denied.
5. Destroyed mailboxes reject all future writes, including stale references.

## Routes

All routes are scoped under `/<path>/mail`.

- `GET /<path>/mail`
  - HTTP Mail UI
- `POST /<path>/mail/new`
  - Create mailbox
- `POST /<path>/mail/<address>/send`
  - Send directly to a known address
- `POST /<path>/mail/send`
  - Compose fallback route (address supplied in form/json)
- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Read inbox
- `POST /<path>/mail/<address>/delete/<msg_id>`
  - Delete one message
- `POST /<path>/mail/<address>/destroy`
  - Destroy mailbox and scrub messages

## API Examples

Create mailbox:

```bash
curl -s -X POST "http://localhost:5001/<path>/mail/new"
```

Send using direct address route:

```bash
curl -s -X POST "http://localhost:5001/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"alice"}'
```

Send using fallback compose route:

```bash
curl -s -X POST "http://localhost:5001/<path>/mail/send" \
  -H "Content-Type: application/json" \
  -d '{"address":"<address>","subject":"hello","body":"test message"}'
```

Read inbox:

```bash
curl -s "http://localhost:5001/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```

## Error Semantics

- `400`: missing required fields (for example empty body or missing address)
- `403`: invalid read key for read/delete/destroy
- `404`: mailbox not found
- `410`: mailbox was destroyed and can no longer accept writes
