# HTTP Mail Guide

HTTP Mail is an SMTP-free, IMAP-free messaging mode built into OpSecChat.
It provides inbox-like behavior over HTTP using in-memory mailboxes.

## Security model

- Each mailbox has:
  - a public `address` (safe to share with senders)
  - a private `read_key` (required to read or delete messages)
- Default deny: inbox reads fail without the correct `read_key`.
- Messages are in-memory only and expire after 24 hours.
- Message content is overwritten in memory before deletion.

## Routes

All routes are namespaced under `/<path>/mail`.

- `GET /<path>/mail`
  - HTTP Mail UI.
- `POST /<path>/mail/new`
  - Create mailbox and return JSON with `address` and `read_key`.
- `POST /<path>/mail/send`
  - Send endpoint for non-JavaScript clients/forms.
  - Address is provided in request body (`_address_override` for forms, `address` for JSON).
- `POST /<path>/mail/<address>/send`
  - Send endpoint when address is already in URL.
- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Read inbox.
- `POST /<path>/mail/<address>/delete/<message_id>`
  - Delete one message (requires `read_key` in body).
- `POST /<path>/mail/<address>/destroy`
  - Destroy mailbox and wipe messages (requires `read_key` in body).

## No-JavaScript send flow

For progressive enhancement and text-only browser use, submit this form:

```html
<form method="POST" action="/<path>/mail/send">
  <input type="text" name="_address_override" />
  <input type="text" name="subject" />
  <textarea name="body"></textarea>
  <input type="text" name="sender" />
  <button type="submit">Send</button>
</form>
```

This avoids client-side URL rewriting and works without JavaScript.

## Notes for operators

- Treat `read_key` like a password.
- There is no mailbox recovery if `read_key` is lost.
- Destroyed mailboxes reject new writes, including writes from stale in-memory references.
