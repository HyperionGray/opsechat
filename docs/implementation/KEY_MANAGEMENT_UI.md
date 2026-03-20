# Key Management UI

## Summary

OpSecChat now includes a browser key management page at `/keys`.

This page provides a practical user interface for client-side OpenPGP key lifecycle tasks:

- Generate a new ECC key pair in the browser
- Import existing private keys
- Import and label public keys
- Export the locally stored private key
- Delete private/public keys from local browser storage

## Security Model

- Private keys are stored in browser `localStorage` via `static/pgp-manager.js`.
- Key operations are executed in the browser using `static/openpgp.min.js`.
- The server renders the UI only; it does not receive private key material.

## Files Added

- `key_management_routes.py` - Flask route registration for `/keys`
- `templates/key_management.html` - Key management interface
- `static/key-management.css` - Styling for the key management page
- `static/key-management.js` - Browser-side key management handlers
- `tests/test_key_management_routes.py` - Route and template safety checks

## Usage

1. Start the server.
2. Open `/keys`.
3. Generate or import keys.
4. Export a private key backup immediately after generation.

## Notes

- The UI intentionally avoids inline scripts and inline event handlers.
- This keeps the new page compatible with the strict CSP script policy.
