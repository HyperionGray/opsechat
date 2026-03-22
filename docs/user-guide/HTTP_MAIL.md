# HTTP Mail (No SMTP/IMAP)

HTTP Mail provides an inbox-style workflow over plain HTTP endpoints with no external mail infrastructure.

## What it is

- Mailbox address: short public identifier you can share with senders
- Read key: private secret required to read and manage mailbox contents
- In-memory only storage: messages never touch disk
- Auto-expiry: messages are removed after 24 hours

## Security model

- Default deny: inbox reads require a valid `read_key`
- Message content is overwritten in memory before deletion
- Destroying a mailbox scrubs all messages and blocks future writes
- Read-key rotation is supported so compromised keys can be invalidated

## Main routes

All routes are scoped under `/<path>/mail/`:

- `GET /<path>/mail` - HTTP Mail UI
- `POST /<path>/mail/new` - create mailbox (returns `address` and `read_key`)
- `POST /<path>/mail/send` - form fallback send (address in `_address_override`)
- `POST /<path>/mail/<address>/send` - send to a specific mailbox
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - read inbox
- `POST /<path>/mail/<address>/delete/<msg_id>` - delete one message
- `POST /<path>/mail/<address>/rotate-key` - rotate read key
- `POST /<path>/mail/<address>/destroy` - destroy mailbox

## Key rotation workflow

Use read-key rotation when a key might be exposed:

1. Call `POST /<path>/mail/<address>/rotate-key` with current `read_key`
2. Store the returned replacement key securely
3. Discard the old key (it no longer works)

## Non-JS compatibility

The compose flow supports both:

- JavaScript mode: auto-targets `/<path>/mail/<address>/send`
- Non-JS mode: submits to `/<path>/mail/send` using `_address_override`
