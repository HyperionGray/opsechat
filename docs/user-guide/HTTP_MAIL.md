# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over HTTP with no SMTP/IMAP dependency.
It is intended for simple, ephemeral message exchange inside an OpSecChat deployment.

## Security model

- Mailboxes are identified by a public `address` (shareable with senders).
- Reading requires a private `read_key` (default deny).
- Messages are stored in memory only and expire automatically.
- Destroying a mailbox scrubs message contents in memory and marks the mailbox as unusable.

## Mailbox lifecycle

1. Create mailbox: `POST /<path>/mail/new`
2. Share `address` with sender(s)
3. Send messages: `POST /<path>/mail/<address>/send`
4. Read inbox with key: `GET /<path>/mail/<address>/inbox?key=<read_key>`
5. Optionally delete individual messages
6. Destroy mailbox when finished

When a mailbox is destroyed, new writes are rejected even if a stale in-memory reference exists.

## API endpoints

All routes are under `/<path>/mail`.

- `GET /<path>/mail`
  - Returns the HTTP Mail UI page

- `POST /<path>/mail/new`
  - Creates a mailbox
  - Response fields:
    - `address`
    - `read_key`
    - `send_url`
    - `inbox_url`

- `POST /<path>/mail/<address>/send`
  - Sends a message
  - Accepts JSON or form data: `subject`, `body`, `sender`
  - Returns `410` if mailbox is no longer available

- `GET /<path>/mail/<address>/meta?key=<read_key>`
  - Authenticated mailbox metadata without message bodies
  - Response fields:
    - `address`
    - `created_at`
    - `message_count`

- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Returns full message list

- `POST /<path>/mail/<address>/delete/<msg_id>`
  - Deletes one message (requires `read_key`)

- `POST /<path>/mail/<address>/destroy`
  - Destroys mailbox (requires `read_key`)

## Operational notes

- `MAX_MAIL_MESSAGE_LENGTH` limits message body size.
- Expiry window is controlled by `MAIL_EXPIRY_HOURS`.
- Storage is process memory, so restarting the app clears all HTTP Mail data.
