# HTTP Mail Guide

**Date:** 2026-03-21  
**Audience:** Operators and developers

## Overview

HTTP Mail provides mailbox-style messaging over HTTPS/HTTP with no SMTP/IMAP dependency.
Each mailbox has:

- A public `address` that senders can use to deliver messages
- A private `read_key` that is required to read or delete messages

Default deny behavior is enforced: without the `read_key`, inbox contents are not returned.

## Security Model

- Messages are stored in memory only
- Message expiry is 24 hours
- Message content is overwritten before deletion
- Destroyed mailboxes reject future writes, including writes from stale object references

## Endpoints

All routes are under `/<path>/mail`.

- `GET /<path>/mail`  
  Main HTTP Mail UI
- `POST /<path>/mail/new`  
  Create mailbox; returns `address` and `read_key`
- `POST /<path>/mail/send`  
  Form fallback endpoint (non-JavaScript flows), uses `_address_override`
- `POST /<path>/mail/<address>/send`  
  Send message to mailbox
- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read inbox with valid read key
- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete one message with read key
- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox with read key

## Non-JavaScript Compose Flow

The compose form submits to `POST /<path>/mail/send` and includes:

- `_address_override` (recipient mailbox address)
- `subject` (optional)
- `body` (required)
- `sender` (optional, defaults to `anonymous`)

This enables sending from browsers where JavaScript is disabled.

## API Notes

- JSON clients receive JSON error responses and status codes
- Form clients receive rendered template responses
- Sending to a mailbox that is no longer available may return `410 Gone`

