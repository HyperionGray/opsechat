# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

### Version 2.0.0 - Major Email System Release
This release represents a significant expansion from a simple chat application to a comprehensive secure communication platform. The addition of real email capabilities, automated domain management, and security research tools makes this a powerful toolkit for privacy-conscious users and security professionals.

### Version 1.0.0 - Initial Release
The original dropchat concept: a simple, secure, anonymous chat system built on Tor hidden services with a focus on operational security and ease of use.

---

## Migration Guide

### From 1.x to 2.x
- **Installation Method**: Native installation is now deprecated. Use Docker/Podman Compose or Systemd Quadlets
- **New Features**: Email system is entirely new - no migration needed for chat functionality
- **Configuration**: Email features require optional SMTP/IMAP configuration
- **Dependencies**: New npm dependencies for testing - run `npm install` if developing

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for information on how to contribute to this project.

## Security

For security-related information, see [SECURITY.md](SECURITY.md).