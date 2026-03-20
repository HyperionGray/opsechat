# Key Management

## Overview

OpSecChat now includes a browser-side key management page at `/keys` for handling local PGP keys used by the chat and email tooling.

All key material is managed in the browser:

- Private keys are stored in browser local storage.
- Public keys are stored per contact label in browser local storage.
- No server-side key persistence is performed by this page.

## Features

- Generate a new PGP keypair (ECC / ed25519)
- Import an armored private key
- Export the current private key
- Delete the private key from the current browser
- Add/remove contact public keys
- Clear all stored public keys

## Usage

1. Open `/keys`.
2. Generate or import your private key.
3. Add public keys for contacts you intend to encrypt to.
4. Export and back up your private key securely.

## Security Notes

- Treat exported private key files as sensitive secrets.
- Prefer using a strong passphrase when generating keys.
- Deleting browser storage or using a new browser profile removes locally stored keys.
- This page is intended for local key operations; it does not replace dedicated hardware-backed key management workflows.
