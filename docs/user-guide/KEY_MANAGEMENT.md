# Key Management Guide

This page explains how to use OpSecChat's browser-based key management at:

`/keys`

## What this feature does

- Generates a new PGP key pair in your browser
- Imports an existing private key for decryption
- Stores recipient public keys for encryption workflows
- Exports your public/private keys for backup
- Clears stored keys from browser storage

## Security model

- Private keys are managed client-side in browser storage.
- The `/keys` page does not post private keys to the server.
- If browser storage is cleared, keys are removed unless backed up.

## Usage

1. Open `/keys`.
2. Generate a key pair or import your existing private key.
3. Export and securely back up your private key.
4. Add public keys for recipients you trust.
5. Use OpSecChat features that rely on PGP workflows.

## Operational recommendations

- Use a strong passphrase when generating/importing private keys.
- Back up private keys in an offline secure location.
- Verify public key fingerprints out-of-band before trusting them.
- Rotate keys on compromise or role changes.
