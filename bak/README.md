# Archived/Backup Files

This directory contains code that is not actively used by the main opsechat application.

## Contents

### `tools/`
Experimental file transfer utilities that were developed but are not integrated with the main chat application. These include:
- `send_auto.py` - Adaptive sender with transport fallback (QUIC/UDP/TCP)
- `quic_send.py` - QUIC-based file sending
- `udp_send.py` - UDP-based file sending
- `tcp_send.py` - TCP-based file sending
- `repair_send.py` - Repair mechanism for failed transfers
- `bench_pvrt.py` - Benchmarking tool

### `transfer_sdk/`
A comprehensive file transfer SDK with multiple transport protocols and integrity checking. This appears to be experimental/development code for a robust file transfer system. Key components include:
- Transport implementations (QUIC, UDP, TCP, WebSocket)
- Integrity checking (sender/receiver daemons)
- Blob management and streaming
- Protocol serialization and encoding
- Various receiver/sender daemons

## Why These Were Moved

These directories were moved to `bak/` during repository organization because:
1. They are not imported or used by the main application (`runserver.py`, email system, etc.)
2. They are not documented in the main README or user-facing documentation
3. All tests pass without them
4. They appear to be experimental/development code for features not yet integrated

## If You Need These

If you need to use or integrate these tools:
1. Move them back to the root directory: `git mv bak/tools tools` or `git mv bak/transfer_sdk transfer_sdk`
2. Update the main documentation to explain their purpose
3. Add tests if needed
4. Ensure they integrate properly with the main application

## History

Moved to bak/ during repository assessment and organization (Issue: "pause and assess").
