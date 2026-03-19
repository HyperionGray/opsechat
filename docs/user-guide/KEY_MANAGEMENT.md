# Key Management Guide

This guide covers the session-scoped key management workflow in OpSecChat.

## Overview

The key management page lets you:

- Generate new high-entropy keys
- Import existing key material
- Review key metadata (fingerprint, source, created timestamp)
- Export key material when needed
- Delete keys with in-memory overwrite before removal

Keys are stored in memory only and are tied to the active session.

## Accessing Key Management

1. Open your OpSecChat session URL.
2. Navigate to **Email Inbox**.
3. Click **Manage Keys**.

Direct route pattern:

```text
/<session-path>/keys
```

## Key Actions

### Generate a key

Use **Generate Key** with an optional label. Generated keys use secure random
material suitable for session-scoped encryption workflows.

### Import a key

Paste existing key material into the import form.

Validation:
- Empty key material is rejected
- Very short key material is rejected

### Export a key

Use the **Export** action for a key row. Export returns JSON from:

```text
/<session-path>/keys/export/<key_id>
```

### Delete a key

Use **Delete** on a key row. The server overwrites key material in memory before
removing the record from the in-memory key store.

## Security Notes

- Key data is not persisted to disk by this feature.
- Deleted keys cannot be recovered.
- Exported keys should be handled as sensitive secrets.
- If the server process stops, in-memory keys are lost.
