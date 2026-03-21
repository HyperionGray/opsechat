# HTTP Mail Guide

Date: 2026-03-21  
Audience: Operators and users

## Overview

HTTP Mail provides disposable inboxes over HTTP with no SMTP/IMAP dependency.
Each mailbox has:

- `address` (public, share with senders)
- `read_key` (private, required to read and delete)

Without `read_key`, inbox reads are denied by default.

## Core Endpoints

Assuming your runtime path token is `<path>`:

- `GET /<path>/mail` - HTTP Mail UI
- `POST /<path>/mail/new` - Create mailbox (`address`, `read_key`)
- `POST /<path>/mail/send` - Send using address in request payload/form
- `POST /<path>/mail/<address>/send` - Send directly to known mailbox address
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - Read inbox
- `POST /<path>/mail/<address>/delete/<msg_id>` - Delete one message
- `POST /<path>/mail/<address>/destroy` - Destroy mailbox

## No-JS Compose Support

The compose UI now has a server-side fallback route:

- `POST /<path>/mail/send`

This allows message delivery from plain HTML forms even if JavaScript is
disabled. The form includes `_address_override` as the recipient mailbox
address.

## Mailbox Destruction Safety

Mailbox destruction is now enforced on stale references:

- Once destroyed, a mailbox is removed from global storage.
- Existing in-memory references are marked `destroyed`.
- Future writes through stale references are rejected.
- Existing message content is overwritten before clearing.

This closes a race window where stale objects could otherwise accept writes
after mailbox deletion.
