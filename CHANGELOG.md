# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Complete CI/CD review implementation
- Missing documentation files (LICENSE.md, CHANGELOG.md, CODE_OF_CONDUCT.md)
- Enhanced documentation structure

### Changed
- Improved code organization and documentation

### Security
- Updated jQuery to v3.7.1 to address XSS vulnerabilities (CVE-2020-11023, CVE-2020-11022)

## [2.0.0] - 2024-12-27

### Added
- **Real Email System Integration**
  - SMTP/IMAP support for sending and receiving actual emails
  - Encrypted email inbox with PGP support
  - Raw mode editing for full header control
- **Modern Burner Email System**
  - Multi-burner management with live countdown timers
  - Quick rotation and instant copy functionality
  - Smart stats dashboard
- **Automated Domain Purchasing**
  - Porkbun API integration for domain rotation
  - Budget management with configurable spending limits
- **Security Research Tools**
  - Spoofing detection for unicode lookalikes and typosquatting
  - Phishing simulation with gamified training
  - Security analysis tools for authorized penetration testing
- **Container Deployment Options**
  - Docker/Podman Compose support
  - Systemd Quadlets for production deployment
  - Native systemd integration
- **Comprehensive Testing**
  - Playwright-based end-to-end testing
  - UI functionality testing (script and noscript modes)
  - Security headers validation
  - Responsive design testing

### Changed
- Modernized deployment architecture with container-first approach
- Enhanced security with improved header validation
- Improved user experience with JavaScript-optional design
- Updated documentation structure with comprehensive guides

### Deprecated
- Native installation method (install.sh/uninstall.sh) in favor of containers

### Security
- Enhanced PGP encryption support
- Improved security headers and validation
- Plain text only email rendering for security analysis
- Tor network integration for anonymous communication

## [1.0.0] - 2017-XX-XX

### Added
- Initial release of opsechat (formerly dropchat)
- Basic anonymous chat functionality over Tor
- Ephemeral hidden service creation
- In-memory chat storage with automatic cleanup
- Randomized usernames for enhanced privacy
- No-JavaScript mode support
- Basic Flask web interface

### Security
- Tor network integration for anonymous communication
- No persistent storage of chat data
- Encrypted communication via Tor hidden services