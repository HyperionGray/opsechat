# HTTP Mail Guide

HTTP Mail provides an inbox-like flow over plain HTTP without SMTP/IMAP.
Each mailbox has:

- A public `address` you can share for receiving messages
- A private `read_key` required to read or delete messages

Messages are stored in memory only and expire automatically.

## Core Security Model

- Default deny: inbox reads require the exact `read_key`
- Plain text only: incoming fields are sanitized before storage
- Memory scrubbing: messages are overwritten before deletion
- Ephemeral retention: messages expire after 24 hours

## Web UI Usage

1. Open `/<path>/mail`
2. Create a mailbox and save the returned `address` and `read_key`
3. Share the `address` with senders
4. Read inbox with `address + read_key`

The "Send a Message" form now works with or without JavaScript by posting to
`/<path>/mail/send` and including the recipient mailbox address in the form.

## API Endpoints

- `POST /<path>/mail/new`  
  Create mailbox. Returns `address` and `read_key`.

- `POST /<path>/mail/<address>/send`  
  Send a message directly to a known mailbox address.

- `POST /<path>/mail/send`  
  Send from generic compose forms by providing `address` (or
  `_address_override`) in the request body.

- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read inbox messages (default deny without valid key).

- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete a message (requires `read_key`).

- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox and scrub messages (requires `read_key`).

## Concurrency Safety Note

Mailbox destroy now marks the mailbox as destroyed before stale writers can
append new messages. Any send attempt against a destroyed mailbox is rejected.
