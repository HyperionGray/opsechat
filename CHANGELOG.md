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
- Complete CI/CD review workflow integration
- Amazon Q code review integration
- Comprehensive documentation structure

### Changed
- Updated jQuery to v3.7.1 to address security vulnerabilities (CVE-2020-11023, CVE-2020-11022)
- Improved documentation organization and completeness

### Security
- Resolved jQuery XSS vulnerabilities with latest version update

## [2.0.0] - 2024-12-22

### Added
- **Real Email System Integration**
  - SMTP/IMAP support for actual email sending and receiving
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
  - Live countdown timers with JavaScript integration
  - Quick rotation and one-click generation
  - Instant clipboard copy functionality
  - Smart stats dashboard for tracking active burners
- **Automated Domain Management**
  - Porkbun API integration for automatic domain purchasing
  - Budget management with configurable monthly limits
  - Support for cheap TLD rotation (.xyz, .club, etc.)
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
- **Container Deployment Options**
  - Docker/Podman Compose support for easy deployment
  - Systemd Quadlets integration for production environments
  - Native systemd service management
- **Comprehensive Testing Suite**
  - Playwright-based end-to-end testing
  - UI functionality testing (script and noscript modes)
  - Security headers validation
  - Responsive design testing

### Changed
- Deprecated native installation in favor of containerized deployment
- Improved security with plain text only email display
- Enhanced user experience with optional JavaScript throughout
- Modernized deployment workflows

### Security
- Added comprehensive security documentation
- Implemented security headers validation
- Enhanced PGP encryption support throughout email system
- Improved anonymous communication features

## [1.0.0] - 2017-XX-XX

### Added
- **Core Chat System**
  - Ephemeral hidden service chat via Tor network
  - In-memory only operation (no disk storage)
  - Disappearing messages (3-minute deletion cycle)
  - Randomized usernames for enhanced anonymity
  - No-configuration-required setup
- **Tor Integration**
  - Automatic ephemeral hidden service creation
  - Encrypted communication through Tor network
  - Attribution-resistant chat environment
- **Dual JavaScript Support**
  - Full functionality with JavaScript disabled (noscript mode)
  - Enhanced user experience with JavaScript enabled
  - Tor Browser compatibility optimization
- **Basic Security Features**
  - No frills, reviewable codebase
  - Low barrier to entry
  - No client software required
  - Minimal dependencies

### Security
- End-to-end encryption via Tor hidden services
- No persistent data storage
- Anonymous session management
- Secure random ID generation for ephemeral use

---

## Release Notes

### Version 2.0.0 - Major Feature Release
This release represents a significant expansion of opsechat beyond simple chat functionality. The addition of real email capabilities, automated domain management, and comprehensive security research tools makes this a complete privacy-focused communication platform.

### Version 1.0.0 - Initial Release
The original dropchat concept focused on providing simple, anonymous chat capabilities over the Tor network with minimal setup and maximum privacy.
### Version 2.0.0 - Major Email System Release
This release represents a significant expansion from a simple chat application to a comprehensive secure communication platform. The addition of real email capabilities, automated domain management, and security research tools makes this a powerful toolkit for privacy-conscious users and security professionals.

### Version 1.0.0 - Initial Release
The original dropchat concept: a simple, secure, anonymous chat system built on Tor hidden services with a focus on operational security and ease of use.

---

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
- **Installation Method**: Native installation is now deprecated. Use Docker/Podman Compose or Systemd Quadlets
- **New Features**: Email system is entirely new - no migration needed for chat functionality
- **Configuration**: Email features require optional SMTP/IMAP configuration
- **Dependencies**: New npm dependencies for testing - run `npm install` if developing

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for information on how to contribute to this project.

## Security

For security-related information, see [SECURITY.md](SECURITY.md).
