# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive CI/CD review integration
- Complete documentation suite including CHANGELOG.md and CODE_OF_CONDUCT.md
- Enhanced security documentation and vulnerability tracking

### Changed
- Improved repository structure and documentation organization
- Updated CI/CD compliance for better maintainability

### Security
- Continued jQuery 3.7.1 usage addressing CVE-2020-11023 and CVE-2020-11022

## [2.0.0] - 2024-12-08

### Added
- **Real Email System Integration**
  - SMTP/IMAP support for sending and receiving actual emails
  - Encrypted email inbox with PGP support
  - Raw mode editing for full email header control
- **Modern Burner Email System**
  - Multi-burner management with simultaneous active addresses
  - Live countdown timers with JavaScript integration
  - Quick rotation and one-click generation
  - Instant clipboard copying functionality
  - Smart stats dashboard for burner tracking
- **Automated Domain Management**
  - Porkbun API integration for domain purchasing (.xyz, .club, etc.)
  - Budget management with configurable monthly spending limits
  - Automated domain rotation for enhanced privacy
- **Security Research Tools**
  - Spoofing detection for unicode lookalikes and typosquatting
  - Phishing simulation with gamified training and scoring
  - Security awareness training tools
- **Enhanced Deployment Options**
  - Systemd Quadlets support for production deployment
  - Docker/Podman Compose integration
  - Native systemd service management
- **Comprehensive Testing Suite**
  - Playwright end-to-end testing framework
  - Automated UI and functionality testing
  - Security headers validation
  - Responsive design testing

### Changed
- **Modernized Infrastructure**
  - Container-first deployment approach
  - Deprecated native installation in favor of containers
  - Improved security isolation through containerization
- **Enhanced User Experience**
  - JavaScript-optional design throughout
  - Improved responsive design
  - Better error handling and user feedback
- **Security Improvements**
  - Updated jQuery to 3.7.1 (security patches)
  - Enhanced input sanitization
  - Improved session management
  - Plain text email rendering for security analysis

### Deprecated
- Native installation scripts (install.sh, uninstall.sh)
  - Now require ALLOW_DEPRECATED_INSTALL=1 environment variable
  - Containers and quadlets are the recommended deployment methods

### Security
- **jQuery Security Update**: Updated to jQuery 3.7.1 to address XSS vulnerabilities
- **Enhanced Input Validation**: Improved sanitization across all user inputs
- **Container Security**: Isolated execution environment for better security posture

## [1.0.0] - 2017-12-01

### Added
- **Core Chat Functionality**
  - Ephemeral Tor hidden service creation
  - Anonymous chat with randomized usernames
  - In-memory message storage (no disk persistence)
  - Auto-expiring messages (3-minute cleanup)
  - JavaScript and no-JavaScript modes
- **PGP Encryption Support**
  - End-to-end encryption using PGP keys
  - Optional encryption for enhanced security
  - Key management and validation
- **Security Features**
  - Tor network integration for anonymity
  - No data persistence to disk
  - Randomized session identifiers
  - Security-focused design principles
- **Basic Documentation**
  - Installation and usage instructions
  - Security recommendations
  - Platform compatibility information

### Security
- **Tor Integration**: All communications routed through Tor network
- **Ephemeral Services**: New hidden service created for each session
- **Memory-Only Storage**: No chat data written to disk
- **Anonymous Design**: No user tracking or identification

---

## Version History Summary

- **v2.0.0**: Major expansion with email system, domain management, and modern deployment
- **v1.0.0**: Initial release with core anonymous chat functionality

## Migration Notes

### From v1.x to v2.x
- **Deployment Method**: Consider migrating from native installation to containers
- **New Features**: Email system and domain management are optional additions
- **Security**: jQuery updated - ensure static files are properly updated
- **Configuration**: New configuration options for email and domain services

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for information about contributing to this project.

## Security

For security-related information and reporting vulnerabilities, see [SECURITY.md](SECURITY.md).