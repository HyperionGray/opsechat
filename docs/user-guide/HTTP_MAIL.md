# HTTP Mail User Guide

HTTP Mail provides mailbox-style messaging over plain HTTP endpoints, without SMTP/IMAP setup.

## Security model

- Each mailbox has:
  - a public `address` (safe to share with senders)
  - a private `read_key` (required to read/delete/destroy)
- Inbox reads are default-deny without the correct `read_key`.
- Messages are in-memory only and expire automatically after 24 hours.
- Destroying a mailbox wipes all messages and permanently blocks further writes to that mailbox instance.

## Route summary

Base path prefix is `/<path>/mail`.

- `GET /<path>/mail`  
  Open HTTP Mail UI.

- `POST /<path>/mail/new`  
  Create mailbox. Returns JSON with `address` and `read_key`.

- `POST /<path>/mail/<address>/send`  
  Send to known mailbox address.

- `POST /<path>/mail/send`  
  Generic send endpoint (address passed in payload).  
  This enables non-JavaScript form posting and API clients that prefer one fixed endpoint.

- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read messages with valid key.

- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete one message with `read_key`.

- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox with `read_key`.

## API examples

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

Send via generic endpoint:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/send" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "MAILBOX_ADDRESS",
    "subject": "hello",
    "body": "test message",
    "sender": "alice"
  }'
```

Read inbox:

```bash
curl -s "http://localhost:5000/<path>/mail/MAILBOX_ADDRESS/inbox?key=READ_KEY"
```

Destroy mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/MAILBOX_ADDRESS/destroy" \
  -H "Content-Type: application/json" \
  -d '{"read_key":"READ_KEY"}'
```
