# HTTP Mail Guide

## Overview

HTTP Mail provides mailbox-style messaging over plain HTTP without SMTP or IMAP.
Each mailbox has:

- `address`: public identifier that senders can use
- `read_key`: private secret required to read or manage that mailbox

Without the read key, mailbox contents are not returned.

## Security Model

- Default deny for reads (`GET inbox` requires `read_key`)
- Messages are stored in memory only
- Expired/deleted messages are overwritten before removal
- Mailboxes can be destroyed, which invalidates old references
- Read keys can be rotated if compromise is suspected

## Quick Start

1. Open `/<path>/mail`
2. Create a mailbox
3. Save the read key immediately
4. Share only the mailbox address with senders
5. Read mailbox using address + read key

## API Endpoints

All routes are scoped under `/<path>/mail`:

- `GET /<path>/mail`
  - Main HTTP Mail UI
- `POST /<path>/mail/new`
  - Create mailbox
  - Returns `address`, `read_key`, `send_url`, `inbox_url`
- `POST /<path>/mail/send`
  - Send message using form/JSON body field `address`
  - Form field: `_address_override`
- `POST /<path>/mail/<address>/send`
  - Send message to explicit mailbox address
- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Read inbox
- `POST /<path>/mail/<address>/delete/<message_id>`
  - Delete message (requires `read_key`)
- `POST /<path>/mail/<address>/rotate-key`
  - Rotate read key using current read key
- `POST /<path>/mail/<address>/destroy`
  - Destroy mailbox and all messages

## Read Key Rotation

Rotate a mailbox read key if the secret may have leaked:

- Provide current read key to `/rotate-key`
- Server returns a newly generated read key
- Old key stops working immediately
- Inbox messages remain available under the new key

## Operational Notes

- Messages expire after 24 hours
- Empty old mailboxes are cleaned up by storage maintenance
- The default UI supports both JavaScript and form-post workflows
