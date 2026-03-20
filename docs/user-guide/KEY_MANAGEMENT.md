# Key Management Guide

This guide covers the browser-only key management page at `/keys`.

## What this feature does

The key management page lets a user:

- Generate a new AES-256-GCM key in the browser
- Import an existing base64-encoded AES key
- Export/copy the current key for backup
- Delete the local key from browser storage
- View a short fingerprint of the key for verification

## Security model

- Keys are generated with the browser Web Crypto API.
- Keys are stored in browser local storage only.
- Keys are never sent to the server by this page.
- If a stored key is invalid, it is removed automatically.

## How to use

1. Open `/keys`.
2. Choose one:
   - `Generate Key` to create a fresh key.
   - Paste a base64 key and click `Import Key`.
3. Use `Copy Key` to securely back up the current key.
4. Use `Delete Local Key` to erase it from this browser.

## Notes

- Exported key format is base64-encoded raw AES key bytes.
- Valid key length is 32 bytes (AES-256).
- Anyone with a copied key can decrypt data protected by that key.
