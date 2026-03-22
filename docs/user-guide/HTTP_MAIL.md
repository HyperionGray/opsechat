# HTTP Mailboxes

HTTP Mailboxes provide an email-like workflow without SMTP/IMAP dependencies.
Messages are posted over HTTP to a mailbox address and read back only with a
private `read_key`.

## Security model

- Default deny for inbox reads: wrong or missing `read_key` returns access denied.
- Mail data is in-memory only.
- Message bodies are length-limited and sanitized by route handlers.
- Mailbox destroy overwrites message content in memory before clearing.
- Destroyed mailbox objects reject stale post-destroy writes to prevent races.

## Endpoints

All routes are registered under `/{path}/mail`.

- `GET /{path}/mail`  
  Render mailbox UI.

- `POST /{path}/mail/new`  
  Create a mailbox. Returns:
  - `address` (shareable receive token)
  - `read_key` (private secret for inbox access/deletes)
  - `send_url`
  - `inbox_url`

- `POST /{path}/mail/{address}/send`  
  Send a message to mailbox address (no auth required to send).
  - `404` when mailbox does not exist
  - `410` when a destroy operation races with send and mailbox is already destroyed

- `GET /{path}/mail/{address}/inbox?key={read_key}`  
  Read inbox contents.
  - `403` for invalid key
  - `404` for unknown mailbox

- `POST /{path}/mail/{address}/delete/{msg_id}`  
  Delete a single message (requires `read_key` in request body/form).

- `POST /{path}/mail/{address}/destroy`  
  Destroy mailbox and scrub message memory (requires `read_key`).

## Typical flow

1. Create mailbox with `POST /{path}/mail/new`.
2. Share `address` with senders.
3. Keep `read_key` private.
4. Read and manage messages through inbox/delete routes.
5. Destroy mailbox when no longer needed.

## Testing

Use:

```bash
PYTHONPATH=. pytest tests/test_http_mail.py -q
```

This validates mailbox creation, send/read/delete/destroy behavior, and route-level access controls.
