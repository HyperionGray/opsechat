# Key Management (`/keys`)

OpSecChat now includes a dedicated key-management page at `/keys` for browser-side key operations.

## What it does

- Generate a new OpenPGP keypair in the browser
- Import an existing armored private key (`.asc` / `.txt`)
- Import an existing armored public key (`.asc` / `.txt`)
- Export private/public keys to local files
- Delete locally stored keys
- Show key status and a public-key preview

## Security model

- Keys are stored in browser `localStorage` only.
- The server does not persist private keys.
- Private key recovery is not possible server-side.

## Workflow

1. Open `/keys`.
2. Click **Generate New Key Pair**.
3. Export private key and store it securely.
4. Share only the public key with contacts.
5. Import keys later on another device if needed.

## Notes

- This page is compatible with strict CSP because scripts and styles are external.
- Key generation uses OpenPGP.js in the browser.
