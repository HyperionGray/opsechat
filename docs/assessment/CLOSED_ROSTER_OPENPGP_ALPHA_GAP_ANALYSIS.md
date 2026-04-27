# Closed-Roster OpenPGP Alpha Gap Analysis

**Date:** 2026-04-26

## Alpha Scope That Is Implemented

The simple room path now supports this narrower but defensible alpha scope:

- immutable closed-roster rooms
- explicit epoch-1 bootstrap
- local OpenPGP identity generation/import in the room UI
- explicit private-key export/download and restore guidance in the room UI
- per-member public-key roster records
- signed and encrypted OpenPGP room messages
- local trust states for `new`, `known`, `changed`, and `verified`
- fail-closed client-side checks for room id, epoch, roster hash, sender, and recipient set
- retirement of the old shared room-key endpoint
- real-app browser smoke coverage for key backup/restore and a two-member encrypted round trip in Chromium

## Release Recommendation

This can ship today as an **alpha** if the release notes are explicit about the current scope:

- room rosters are immutable after bootstrap
- key changes require a new room
- the browser is still the crypto owner for simple rooms
- intended-recipient packet subpacket verification is not yet enforced

## Remaining Gaps

### 1. Epoch transitions are not implemented yet

Still missing:

- signed roster-change proposals
- unanimous approvals from the current roster
- candidate acknowledgements
- activation of epoch 2+

Impact:

- add/remove/key-rotation is not available inside an active room

Alpha stance:

- acceptable if documented as "create a new room for any membership change"

### 2. Browser-only crypto owner

Still missing:

- TUI-first or local-process key owner
- external local trust store outside the browser session

Impact:

- simple rooms still rely on browser session storage for the local private key

Alpha stance:

- acceptable, but it is the largest architectural gap versus the original plan

### 3. Packet-level recipient subpacket work

Still missing:

- intended-recipient subpacket generation/verification
- deeper recipient packet parsing beyond explicit key-id checks

Impact:

- recipient-set validation is strong for this alpha, but not yet as complete as the full plan target

Alpha stance:

- acceptable if called out as a known protocol gap

### 4. Broader browser automation still needs expansion

Still missing:

- Firefox/WebKit coverage for the real-app room smoke
- automated negative cases for changed-key alarms
- broader browser automation for room recreation after key rotation

Current coverage:

- focused Python suites for room bootstrap, room state, envelope validation, and room policy
- real-app Chromium Playwright smoke for key export/re-import and a two-member encrypted-message round trip

Impact:

- the core alpha path is now browser-smoke-tested on the real app, but multi-browser and negative-path coverage is still thin

Alpha stance:

- acceptable if one manual two-browser smoke test is completed before tagging

### 5. Key lifecycle beyond backup is still thin

Still missing:

- revocation or key-roll workflow
- persistent trust-store export/import outside browser session storage
- stronger operator workflow for deliberate room recreation after a key change

Impact:

- operators can now back up and restore the local private key, but longer-term key lifecycle handling is still minimal

Alpha stance:

- acceptable for alpha, but not for a broader beta

## Suggested Same-Day Alpha Checklist

1. Do one manual two-browser smoke test:
   - bootstrap a room
   - verify both sides can decrypt and validate messages
   - export and re-import one participant's private key
2. Call out the immutable-roster limitation in the release notes
3. Call out that `/chat/room/<room_id>/key` is intentionally retired
4. Keep the release scoped to simple rooms; do not claim full room-member rotation support

## Post-Alpha Priority Order

1. Signed epoch-transition workflow
2. TUI/local-process crypto owner
3. Expand real-app browser automation across Firefox/WebKit and changed-key negatives
4. Intended-recipient subpacket support
5. Key revocation and rotation UX
