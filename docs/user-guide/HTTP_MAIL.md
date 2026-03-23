# HTTP Mailboxes (Email-over-HTTP)

Last Updated: 2026-03-23

HTTP Mailboxes provide lightweight message passing over HTTP with no SMTP/IMAP dependency.
Each mailbox has:

- a public `address` (share this with senders)
- a private `read_key` (required to read or delete content)

The system is default-deny for reads: a valid `read_key` is required to access inbox data.

## Security and Data Handling

- In-memory only storage (no mailbox/message persistence to disk)
- Message expiry after 24 hours
- Message body/subject/sender overwrite before deletion
- Mailbox destroy operation marks mailbox as unusable to block stale-reference writes

If a mailbox is destroyed while a sender still holds an old mailbox reference, new sends are refused.

## Routes

All routes are namespaced under:

`/<path>/mail`

Where `<path>` is the server path token configured by the app.

### Create mailbox

`POST /<path>/mail/new`

Response:

```json
{
  "success": true,
  "address": "mailbox-address",
  "read_key": "private-read-key",
  "send_url": "/<path>/mail/<address>/send",
  "inbox_url": "/<path>/mail/<address>/inbox"
}
```

### Send message

`POST /<path>/mail/<address>/send`

Accepts JSON or form fields:

- `subject` (optional)
- `body` (required)
- `sender` (optional, defaults to `anonymous`)

Status codes:

- `200` message accepted
- `404` mailbox not found
- `410` mailbox no longer available (destroyed lifecycle state)

### Read inbox

`GET /<path>/mail/<address>/inbox?key=<read_key>`

Status codes:

- `200` success
- `403` invalid or missing key
- `404` mailbox not found

### Delete message

`POST /<path>/mail/<address>/delete/<msg_id>`

Requires `read_key` in JSON or form body.

### Destroy mailbox

`POST /<path>/mail/<address>/destroy`

Requires `read_key` in JSON or form body.
On success, mailbox content is scrubbed in memory and mailbox is marked destroyed.

## Quick Example

```bash
# 1) Create mailbox
curl -s -X POST "http://localhost:5000/<path>/mail/new"

# 2) Send message
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test","sender":"alice"}'

# 3) Read inbox
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>"
```
