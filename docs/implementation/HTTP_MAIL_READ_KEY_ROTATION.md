# HTTP Mail Read-Key Rotation

## Summary

The HTTP mailbox system now supports **read-key rotation**. This lets mailbox owners invalidate the current private read key and immediately switch to a new one without creating a new mailbox address.

This improves operational security when a key may have been exposed.

## What was added

- New route: `POST /<path>/mail/<address>/rotate-key`
- JSON API support and form-post support
- Browser UI button in HTTP Mail "Danger Zone" to rotate key
- Automatic inbox input update in JavaScript UI after rotation
- Tests for successful rotation, invalid key handling, and old-key invalidation

## API behavior

### Request

`POST /<path>/mail/<address>/rotate-key`

Body:

- JSON: `{"read_key": "<current_key>"}`
- or form data: `read_key=<current_key>`

### Success response

```json
{
  "success": true,
  "new_read_key": "..."
}
```

### Failure response

- `403` when key is invalid or mailbox does not exist

## Security notes

- The old read key becomes invalid immediately.
- Existing mailbox address remains unchanged.
- Message data remains in-memory only.
- Mailbox destroy now uses an explicit `destroyed` state and message overwrite path to reduce race-condition risk during deletion.

