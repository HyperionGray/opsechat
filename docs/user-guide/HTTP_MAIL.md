# HTTP Mail (Email over HTTP)

`HTTP Mail` provides inbox-style messaging without SMTP/IMAP dependencies.
Mailboxes are in-memory only and access is default-deny.

## Overview

- Create a mailbox at `/<path>/mail`
- Receive:
  - Public mailbox `address` (shareable)
  - Private `read_key` (secret, required to read/delete/destroy)
- Senders can post messages to `/<path>/mail/<address>/send`
- Inbox readers use `/<path>/mail/<address>/inbox?key=<read_key>`

## Security Model

- No valid `read_key` -> no message visibility
- Messages expire after 24 hours
- Deleted/expired/destroyed messages are overwritten in memory before removal
- Mailboxes are removed from global lookup during destruction to block new lookups

## New Lifecycle + Capacity Behavior

As of March 2026:

- Each mailbox now has a hard capacity limit of `500` messages
  - Additional sends return `429` with a mailbox-full error
- Destroyed mailboxes now reject concurrent writes explicitly
  - Writes against a mailbox already marked destroyed return `410`

This closes a race window where a sender could hold a stale mailbox reference
while a destroy operation was in progress.

## API Summary

### Create mailbox

`POST /<path>/mail/new`

Response fields:

- `address`
- `read_key`
- `send_url`
- `inbox_url`
- `max_messages_per_mailbox`

### Send message

`POST /<path>/mail/<address>/send`

Possible outcomes:

- `200`: queued successfully
- `404`: mailbox not found
- `410`: mailbox destroyed/unavailable
- `429`: mailbox full

### Read inbox

`GET /<path>/mail/<address>/inbox?key=<read_key>`

- `200`: returns messages
- `403`: invalid/missing read key
- `404`: mailbox not found

### Delete message

`POST /<path>/mail/<address>/delete/<msg_id>`

- Requires `read_key`

### Destroy mailbox

`POST /<path>/mail/<address>/destroy`

- Requires `read_key`
- Overwrites and removes all retained messages

