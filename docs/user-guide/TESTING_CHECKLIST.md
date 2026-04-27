# Testing Checklist - Closed-Roster Alpha

Use this checklist for the current simple-room alpha flow.

## Automated Checks

Run the focused suites:

```bash
pytest -q tests/test_openpgp_room_policy.py tests/test_simple_chat_routes.py tests/test_chat_endpoints.py tests/test_security_headers.py
```

For the real room UI smoke on the actual Flask app:

```bash
npx playwright install chromium
npx playwright test tests/closed-roster-openpgp-real-app.spec.js --project=chromium-headless --reporter=line
```

Expected:

- room policy tests pass
- room bootstrap and envelope tests pass
- deprecated shared-key endpoint returns `410`
- security headers still pass
- the real-app Chromium smoke passes key export/re-import and a two-member encrypted round trip

## Manual Browser Smoke Test

### 1. Bootstrap a room

1. start the server
2. open `/chat`
3. create a room
4. generate or import Alice's identity
5. add Bob's public key
6. verify Bob locally
7. lock the roster

Expected:

- epoch 1 appears
- a roster hash is shown
- send stays disabled until verification is complete

### 2. Join from a second browser/session

1. open the same room URL
2. import Bob's identity
3. verify Alice locally

Expected:

- Bob sees the active roster
- Bob sees Alice as pending until verified locally
- send becomes enabled after local verification

### 2a. Backup and restore the local identity

1. click `Download Private Key`
2. confirm the room no longer warns about a missing backup export
3. click `Clear Local Identity`
4. re-import the downloaded private key

Expected:

- the room shows the backup export timestamp
- the local identity can be restored without changing fingerprints
- the room does not treat the restored key as a key change

### 3. Exchange a message

1. Alice sends a message
2. Bob receives it
3. Bob replies

Expected:

- both sides can decrypt
- both sides see accepted messages
- sender identity matches the roster entry

### 4. Negative smoke test

Try at least one of these:

- use a local identity not present in the roster
- alter a posted message payload with the browser dev tools
- reload a passphrase-protected identity without re-entering the passphrase

Expected:

- send is blocked or the message is rejected
- the UI shows a clear failure state

## API Spot Checks

### Fetch room state

```bash
curl http://localhost:5001/chat/room/<room_id>/state
```

Expected:

- `mode` is `closed_roster_openpgp_v1`
- `policy.immutable_roster` is `true`

### Deprecated key endpoint

```bash
curl http://localhost:5001/chat/room/<room_id>/key
```

Expected:

- HTTP `410`

### Direct messages

```bash
curl -X POST http://localhost:5001/chat/dm/send \
  -H "Content-Type: application/json" \
  -d '{"room_id":"test-room","message":"join here"}'
```

Expected:

- DM is created
- DM expires after 60 seconds
