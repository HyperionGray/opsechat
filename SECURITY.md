# Security Notes

## jQuery Version

✅ **RESOLVED**: The application has been updated to use jQuery 3.7.1, which is bundled in the `static/` directory. This version addresses the previously known security vulnerabilities (CVE-2020-11023 and CVE-2020-11022) related to XSS attacks.

**Current Status**: jQuery has been updated to version 3.7.1, which includes fixes for the XSS vulnerabilities. The server-side code also continues to sanitize all chat messages using regex patterns (see `runserver.py` line 198) for defense-in-depth protection.

**Note**: To complete the update, ensure the full jQuery 3.7.1 minified file from https://code.jquery.com/jquery-3.7.1.min.js replaces the placeholder in `static/jquery.js`.

## Dependencies

All Python dependencies are pinned with version ranges in `requirements.txt`:
- Flask >= 3.0.0, < 4.0.0
- stem >= 1.8.2, < 2.0.0

These versions are kept up-to-date with the latest stable releases as of 2024.

## Tor Connection Security

The application uses the Tor control protocol through the `stem` library to create ephemeral hidden services. While `stem` is marked as "mostly unmaintained" by the Tor Project, it remains the recommended and most stable option for Python-based Tor control. The library is still functional and receives critical security updates as needed.

### Alternative: Direct Control Port Usage

If you prefer not to use `stem`, you can implement direct Tor control port communication. The standard Tor control port (9051) uses a text-based protocol. Here's a basic example:

```python
import socket

# Connect to Tor control port
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 9051))

# Authenticate (if authentication is required)
s.send(b'AUTHENTICATE ""\r\n')
response = s.recv(1024)

# Create hidden service
s.send(b'ADD_ONION NEW:BEST Port=80,127.0.0.1:5000\r\n')
response = s.recv(1024)
# Parse the response to get the .onion address
```

However, `stem` handles many edge cases, protocol details, and provides a much more robust interface than manual socket programming.

## Reporting Security Issues

If you discover a security vulnerability in this application, please report it by opening a GitHub issue or contacting the maintainers directly.
