# HTTP Mail Guide

## Overview

HTTP Mail provides mailbox-style messaging without SMTP/IMAP. A mailbox is identified by:

- `address` (shareable, used by senders)
- `read_key` (secret, required to read or delete)

Messages are in-memory only and expire automatically.

## Core Endpoints

- `POST /<path>/mail/new`  
  Create a mailbox and return `address` + `read_key`.
- `POST /<path>/mail/<address>/send`  
  Send to a mailbox address.
- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read messages with the correct `read_key`.
- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete a message with `read_key`.
- `POST /<path>/mail/<address>/destroy`  
  Destroy the entire mailbox with `read_key`.

## Security Model

- Default deny: inbox reads require exact `read_key`.
- All data is in memory.
- Message content is overwritten before deletion.
- Message body length is capped (`MAX_MAIL_MESSAGE_LENGTH`).

## Destroyed Mailbox Behavior

Mailbox destruction is race-safe and explicit:

- Once destroyed, the mailbox is removed from active storage.
- Any stale writer reference is blocked (`MailboxDestroyedError`).
- Destroyed addresses are tombstoned briefly to avoid ambiguous failures.

### Status Codes for Destroyed Addresses

- `410 Gone` is returned for recently destroyed mailboxes when calling:
  - send
  - inbox read
  - repeated destroy
- `404 Not Found` is still used for unknown addresses that were never seen (or whose tombstone expired).

This separation helps clients distinguish:

1. Wrong/unknown address (`404`)
2. Valid address that has been intentionally destroyed (`410`)
