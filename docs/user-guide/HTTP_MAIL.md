# HTTP Mail User Guide

HTTP Mail provides disposable inboxes over plain HTTP with no SMTP/IMAP dependencies.

## Security model

- Each mailbox has a **public address** (share with senders)
- Each mailbox has a **private read key** (required to read/delete/destroy)
- Reading is **default deny** without the correct read key
- Messages auto-expire after 24 hours
- Message content is overwritten in memory before deletion

## Endpoints

All routes are scoped under `/<path>/mail`.

- `GET /<path>/mail`  
  Open the HTTP Mail UI.
- `POST /<path>/mail/new`  
  Create a mailbox and return `address` + `read_key`.
- `POST /<path>/mail/<address>/send`  
  Send to a mailbox by explicit address.
- `POST /<path>/mail/send`  
  **No-JS compose endpoint**. Address is provided in request body (`_address_override` for form posts, `address` for JSON).
- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read mailbox messages.
- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete one message (requires `read_key`).
- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox and wipe message data.

## No-JS compose flow

1. Open `/<path>/mail`
2. Select **Send a Message**
3. Fill mailbox address, subject/body, and optional sender handle
4. Submit the form (posts to `/<path>/mail/send`)

This path works without JavaScript and is suitable for hardened browser configurations.

## Operational notes

- Destroyed mailboxes reject further writes, including late writers holding stale references.
- For JSON clients, mailbox-destroy races during send return `410 Gone`.
