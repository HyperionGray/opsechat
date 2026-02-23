# PGP Support in OpSechat

OpSechat now includes built-in PGP encryption support for enhanced message security.

## Features

- **Client-side encryption/decryption**: All PGP operations happen in the browser using OpenPGP.js
- **Automatic encryption**: Messages are automatically encrypted when public keys are configured
- **Seamless decryption**: Encrypted messages are automatically decrypted when viewing
- **No server-side storage**: Keys are stored only in your browser's localStorage
- **Visual indicators**: Lock icons (🔒) show when messages are encrypted

## How to Use

### Setting Up PGP

1. Click on "⚙️ PGP Settings" link in the chat interface
2. The settings modal will open with two sections:

#### Private Key (For Decryption)
- Import your PGP private key to decrypt messages from others
- If your key is password-protected, enter the passphrase
- Click "Import Private Key"
- Your key is stored locally in your browser only

#### Public Keys (For Encryption)
- Add public PGP keys of other chat participants
- Optionally provide a username identifier
- Click "Add Public Key"
- Messages will be automatically encrypted for all users with stored public keys

### Sending Encrypted Messages

Once you've configured public keys:
1. Type your message normally
2. Press Enter
3. The message is automatically encrypted before sending
4. Other users with the corresponding private key can decrypt and read it

### Reading Encrypted Messages

Once you've configured your private key:
1. Encrypted messages appear with a 🔒 icon
2. They are automatically decrypted and displayed
3. If decryption fails, you'll see "[Failed to decrypt message]"

### Status Indicators

The PGP status indicator shows:
- `🔓 Can decrypt` - Private key is configured
- `🔒 Will encrypt` - Public keys are configured
- `❌ PGP not configured` - No keys configured

## Security Notes

- Keys are stored in browser localStorage (not on the server)
- Private keys should be password-protected for additional security
- Share public keys through secure channels
- PGP messages are much longer than regular messages
- Messages without PGP keys configured are sent as plaintext

## Generating PGP Keys

If you don't have PGP keys, you can generate them using:

### Command Line (GPG)
```bash
gpg --gen-key
gpg --armor --export your-email@example.com > public-key.asc
gpg --armor --export-secret-keys your-email@example.com > private-key.asc
```

### Online Tools
- Mailvelope (browser extension)
- Keybase
- Other PGP key generation tools

## Technical Details

- Uses OpenPGP.js v5.11.0 for all cryptographic operations
- RSA and ECC keys are supported
- Messages are encrypted for all configured public keys simultaneously
- PGP messages bypass the normal character sanitization to preserve encryption data
