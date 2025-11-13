# Security Notes

## jQuery Version

The application currently uses jQuery 3.3.1, which is bundled in the `static/` directory. This version has known security vulnerabilities (CVE-2020-11023 and CVE-2020-11022) related to XSS attacks when using `.html()` or `.append()` with untrusted input.

**Mitigation**: The server-side code sanitizes all chat messages using regex patterns (see `runserver.py` line 198) to remove potentially dangerous characters before they reach the client. This provides defense-in-depth protection.

**Recommendation**: Update `static/jquery.js` to jQuery 3.7.1 or later for additional security. Download from https://code.jquery.com/jquery-3.7.1.min.js

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
