# Simple Chat Rooms

## Overview

Simple chat rooms now use an immutable closed-roster OpenPGP workflow.

The important change is that the room no longer distributes a shared encryption key.

Instead:

- every member has a public key
- the room is explicitly bootstrapped to epoch 1
- every message is signed by the sender
- every message is encrypted to the full roster

## Quick Start

### Local server

```bash
python bin/chat-room.py
```

### Tor hidden service

```bash
tor --ControlPort 9051 --CookieAuthentication 1
python bin/chat-room.py --tor
```

Then open `/chat`.

## Room Lifecycle

### 1. Create the room

- open `/chat`
- create a room
- share the URL only with the people who should be in the room

### 2. Configure the local identity

Inside the room:

- set the local `member_id`
- set the display name
- generate a key pair or import an existing private key
- download the armored private-key backup before you rely on the room
- if you lose the browser session, re-import the same private key to recover access

### 3. Add the roster

Before the first message:

- add every member's public key
- verify fingerprints out of band
- mark every non-local member verified
- lock epoch 1

### 4. Send messages

Once the roster is locked:

- type the message
- click `Sign + Encrypt`
- the browser signs and encrypts the payload to the full roster

## Security Model

### What the room enforces

- explicit active epoch
- explicit roster hash
- sender must be in the roster
- recipient set must match the roster
- wildcard recipients are not allowed
- local trust state is visible to the operator

### Alpha limitation

The active roster is immutable in this release.

If membership changes or a key rotates:

1. stop using the room
2. create a new room
3. bootstrap a new epoch-1 roster

The room UI now includes:

- explicit private-key download/export
- a warning when no backup export is recorded for the current browser session
- recovery guidance for re-importing the same key after session loss

## API Summary

### Create room

```text
POST /chat/create
```

### Fetch room state

```text
GET /chat/room/<room_id>/state
```

### Bootstrap epoch 1

```text
POST /chat/room/<room_id>/state/bootstrap
```

### Fetch or post messages

```text
GET  /chat/room/<room_id>/messages
POST /chat/room/<room_id>/messages
```

### Deprecated endpoint

```text
GET /chat/room/<room_id>/key
```

This endpoint now returns `410 Gone`.
