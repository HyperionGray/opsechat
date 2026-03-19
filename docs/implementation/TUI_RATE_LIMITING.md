## TUI Rate Limiting Implementation

**Date:** 2026-03-19  
**Scope:** `src/tui/server.py`, `src/tui/client.py`, `tests/test_tui_server_rate_limit.py`

### Summary

Implemented server-side per-user message rate limiting for the TUI chat stack to reduce flooding and accidental spam bursts.

### Behavior

- Each connected username is limited to:
  - **8 messages**
  - per **30-second** rolling window
- Limit is enforced in `ChatServer.add_message_with_result(...)`.
- When a user exceeds the cap:
  - The message is rejected.
  - The server sends a structured `rate_limit` event to that client.
  - The client displays a system warning including retry guidance.
- Limits are user-scoped, so one noisy user does not throttle others.

### Security and OpSec Impact

- Reduces flood/spam impact in ephemeral rooms.
- Keeps controls in-memory only (no persistent counters).
- Preserves existing text-only and sanitization controls.

### Compatibility

- Existing `add_message(...) -> bool` behavior remains available.
- New structured API: `add_message_with_result(...)` returns success/error metadata.
- No wire protocol breaking changes for existing `message` and `welcome` events.

### Tests Added

- `test_tui_message_lifetime_is_four_minutes`
- `test_rate_limit_blocks_excess_messages_and_recovers`
- `test_rate_limit_is_scoped_per_user`

These tests verify:
- 4-minute TUI burn lifetime consistency (`240s`)
- Throttling after message burst
- Recovery after window expiry
- Per-user isolation of rate limits
