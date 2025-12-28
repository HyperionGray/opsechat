# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Complete CI/CD review integration
- Code of Conduct for community guidelines
- Comprehensive changelog documentation

### Changed
- Improved documentation structure and completeness
- Enhanced security documentation

### Security
- Updated jQuery to version 3.7.1 to address XSS vulnerabilities (CVE-2020-11023, CVE-2020-11022)

## [2.0.0] - 2024-12-08

### Added
- **Real Email System Integration**
  - SMTP/IMAP support for sending and receiving actual emails
  - Encrypted email inbox with PGP support
  - Raw mode editing for full header control
- **Modern Burner Email System**
  - Multi-burner management with simultaneous active addresses
  - Live countdown timers with JavaScript
  - Quick rotation and one-click generation
  - Instant copy to clipboard functionality
  - Smart stats dashboard for tracking active burners
- **Automated Domain Management**
  - Porkbun API integration for domain purchasing
  - Budget management with configurable spending limits
  - Automatic domain rotation for enhanced privacy
- **Security Research Tools**
  - Spoofing detection for unicode lookalikes and typosquatting
  - Phishing simulation with gamified training
  - Security awareness scoring and achievements
- **Enhanced Deployment Options**
  - Systemd Quadlets for production deployment
  - Docker/Podman Compose support
  - Native systemd integration with automatic startup
- **Comprehensive Testing**
  - Playwright E2E test suite
  - Automated CI/CD workflows
  - Security validation testing

### Changed
- Modernized deployment architecture with container support
- Improved documentation with detailed setup guides
- Enhanced security headers and validation
- Upgraded Flask to version 3.0+ for better security
- Updated Python dependencies with version pinning

### Deprecated
- Native installation method (install.sh/uninstall.sh) in favor of containerized deployment

### Security
- Implemented comprehensive security headers
- Added input sanitization and validation
- Enhanced PGP encryption support
- Improved Tor integration security
- Regular security dependency updates

## [1.0.0] - 2017-12-01

### Added
- Initial release of opsechat (formerly dropchat)
- Basic anonymous chat functionality over Tor
- Ephemeral hidden service creation
- In-memory chat storage with automatic cleanup
- Randomized usernames for enhanced anonymity
- JavaScript and no-JavaScript modes
- Basic PGP encryption support
- Flask web framework integration
- Tor Browser compatibility

### Features
- Anonymous chat rooms via Tor hidden services
- No persistent data storage
- Automatic chat cleanup every 3 minutes
- Randomized color-coded usernames
- Cross-platform client support (any OS with Tor Browser)
- Linux server hosting
- Simple one-command server startup

### Security
- End-to-end encryption via Tor network
- No disk storage of chat data
- Ephemeral hidden services
- Input sanitization
- No user tracking or logging

---

## Release Notes

### Version 2.0.0 - Major Feature Release
This release represents a significant expansion of opsechat beyond simple chat functionality. The addition of real email capabilities, automated domain management, and comprehensive security research tools makes this a complete privacy-focused communication platform.

### Version 1.0.0 - Initial Release
The original dropchat concept focused on providing simple, anonymous chat capabilities over the Tor network with minimal setup and maximum privacy.

## Migration Guide

### From 1.x to 2.x
- **Deployment**: Consider migrating to containerized deployment for better security and maintenance
- **Configuration**: Email features are optional and require additional setup
- **Dependencies**: Update Python dependencies as specified in requirements.txt
- **Testing**: New Playwright test suite available for validation

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for information about contributing to this project.

## Security

For security-related information and reporting vulnerabilities, see [SECURITY.md](SECURITY.md).