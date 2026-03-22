# HTTP Mail (Email over HTTP)

HTTP Mail provides an email-like inbox model without SMTP/IMAP dependencies.
Everything is in memory and access is controlled by a private read key.

## Model

- Mailbox address: short token that senders can use
- Read key: private secret required to read/delete/destroy mailbox contents
- Storage: in-memory only (no mailbox persistence on disk)
- Message expiry: 24 hours

## Endpoints

Routes are mounted under `/<path>/mail`.

- `GET /<path>/mail`  
  Main UI for mailbox creation, sending, and reading.

- `POST /<path>/mail/new`  
  Creates mailbox and returns JSON:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

- `POST /<path>/mail/send`  
  Generic send endpoint (form or JSON).  
  Required fields:
  - `address`
  - `body`  
  Optional:
  - `subject`
  - `sender`

- `POST /<path>/mail/<address>/send`  
  Direct send endpoint for known mailbox addresses.

- `GET /<path>/mail/inbox`  
  Generic inbox read endpoint. Query parameters:
  - `address`
  - `key`
  - `limit` (optional, `1..200`)

- `GET /<path>/mail/<address>/inbox?key=<read_key>&limit=<n>`  
  Direct inbox read endpoint.

- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Deletes one message (requires `read_key`).

- `POST /<path>/mail/<address>/destroy`  
  Destroys mailbox and scrubs message memory (requires `read_key`).

## JavaScript and no-JavaScript behavior

- JS mode:
  - mailbox creation and inbox fetch use `fetch`
  - actions are updated live in the page
- no-JS mode:
  - compose form submits through `POST /<path>/mail/send`
  - inbox form submits through `GET /<path>/mail/inbox`

## Security notes

- Default deny reads: wrong or missing read key returns access denied.
- Mailbox destruction is final:
  - mailbox is removed from global storage
  - messages are overwritten and cleared from memory
  - late writes are rejected on destroyed mailbox objects
- Input is sanitized to plain text for subject/body/sender.

