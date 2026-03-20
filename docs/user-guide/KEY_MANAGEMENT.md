# Key Management Guide

This guide covers the browser-based key management page at `/keys`.

## What this page does

The `/keys` page provides local key operations in the browser:

- Generate a new OpenPGP key pair
- Import an existing armored private key
- Import one or more armored public keys
- Export private key and public key set
- Delete private or public keys with confirmation

## Security model

- Keys are generated and handled client-side with OpenPGP.js.
- Private keys are stored in browser local storage.
- Passphrases are stored in memory only for the active page session.
- The server does not persist private key material from this page.

## Usage

1. Open `/keys`.
2. Use **Generate New Key Pair** to create a new key locally.
3. Use **Import Private Key** if you already have an existing key.
4. Use **Import Public Key** to add contacts' keys by label.
5. Export keys for backup before clearing browser storage.

## Operational notes

- If you lose your private key export, encrypted content is unrecoverable.
- Use a strong passphrase (minimum 8 characters, longer recommended).
- Back up key material securely outside the browser.

## Related documentation

- [PGP Usage](PGP_USAGE.md)
- [Email System](EMAIL_SYSTEM.md)
