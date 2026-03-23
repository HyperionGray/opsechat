# HTTP Mail (SMTP-Free Inboxes)

## Overview

HTTP Mail provides disposable, in-memory mailboxes without SMTP or IMAP.  
It is designed for simple drop-style messaging:

- Share a public mailbox address for receiving messages
- Keep a private read key for inbox access
- Store messages in memory only (no disk persistence)
- Auto-expire messages after 24 hours

## Core Model

Each mailbox has:

- `address` (public): safe to share with senders
- `read_key` (private): required to read and delete messages

Default-deny behavior is enforced: if the `read_key` is missing or incorrect, inbox reads are rejected.

## Endpoints

Base path: `/{path}/mail`

- `GET /{path}/mail`  
  Main HTTP Mail UI

- `POST /{path}/mail/new`  
  Create mailbox, returns JSON with `address`, `read_key`, and helper URLs

- `POST /{path}/mail/{address}/send`  
  Send a message directly to a mailbox address

- `POST /{path}/mail/send`  
  No-JavaScript fallback sender route. Uses form field `_address_override`.

- `GET /{path}/mail/{address}/inbox?key={read_key}`  
  Read inbox (requires `read_key`)

- `POST /{path}/mail/{address}/delete/{message_id}`  
  Delete one message (requires `read_key`)

- `POST /{path}/mail/{address}/destroy`  
  Destroy mailbox and wipe all remaining messages (requires `read_key`)

## Inbox API Filters

When requesting JSON (`Accept: application/json`), inbox reads support:

- `latest=<n>`  
  Returns newest-first subset, with `n` between `1` and `100`

- `summary=1` (or `true`/`yes`)  
  Returns message metadata with `body_preview` and `body_length` instead of full body text

Example:

```bash
curl -H "Accept: application/json" \
  "http://localhost:5000/abc123/mail/MAILBOX_ADDRESS/inbox?key=READ_KEY&latest=5&summary=1"
```

## Security Notes

- Mailboxes can be destroyed; writes to destroyed mailbox objects are rejected.
- Message content is overwritten in memory before deletion.
- Inbox access requires exact key match checks.
- HTML/script-like characters are sanitized for mailbox messages.

