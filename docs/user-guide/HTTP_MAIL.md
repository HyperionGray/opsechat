# HTTP Mail (Email over HTTP)

HTTP Mail is a lightweight mailbox system that does not require SMTP or IMAP.
It is designed for short-lived, anonymous message drops and uses in-memory
storage only.

## Security model

- Each mailbox has:
  - a public `address` (safe to share with senders)
  - a private `read_key` (required to read/delete/destroy)
- Default deny: without the correct `read_key`, inbox reads are rejected.
- Messages auto-expire after 24 hours.
- Message content is overwritten in memory before deletion.

## Access

Open:

`/{path}/mail`

The page supports both JavaScript and no-JavaScript workflows.

## Main flows

### 1) Create mailbox

Click **Create Mailbox** to receive:

- mailbox address
- read key
- sender URL

Save the read key immediately.

### 2) Send message

Use the recipient mailbox address to send a message.
No authentication is required for sending.

### 3) Read inbox

Enter mailbox address + read key to view messages.
Delete individual messages or destroy the entire mailbox from the inbox view.

## HTTP endpoints

- `GET /{path}/mail` - main UI
- `POST /{path}/mail/new` - create mailbox
- `POST /{path}/mail/send` - no-JS compose endpoint
- `POST /{path}/mail/{address}/send` - send to mailbox
- `GET /{path}/mail/inbox` - no-JS inbox endpoint
- `GET /{path}/mail/{address}/inbox?key=...` - read inbox
- `POST /{path}/mail/{address}/delete/{msg_id}` - delete message
- `POST /{path}/mail/{address}/destroy` - destroy mailbox

## Notes

- Data is process-memory only (no mailbox persistence across restart).
- For JSON API usage, send `Accept: application/json`.
