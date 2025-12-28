# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Complete CI/CD review integration
- Amazon Q code review automation
- Comprehensive documentation review system

## [3.0.0] - 2024-12-26

### Added
- **Real Email System Integration**
  - SMTP/IMAP support for sending and receiving actual emails
  - Encrypted email inbox with in-memory storage
  - Raw mode editing for full email header control
  - Plain text only display for security analysis
- **Modern Burner Email System**
  - Guerrillamail-style rotating anonymous email addresses
  - Multi-burner management with simultaneous active addresses
  - Live countdown timers with JavaScript integration
  - Quick rotation and one-click generation
  - Instant clipboard copy functionality
  - Smart stats dashboard for tracking active burners
- **Automated Domain Management**
  - Porkbun API integration for cheap domain rotation (.xyz, .club, etc.)
  - Budget management with configurable monthly spending limits
  - Automated domain purchasing for enhanced anonymity
- **Security Research Tools**
  - Spoofing detection for unicode lookalikes and typosquatting
  - Phishing simulation with gamified training and scoring
  - Achievement system for security awareness training
  - Homograph attack detection
- **Enhanced PGP Support**
  - End-to-end encryption for email communications
  - Key management and validation
  - Seamless integration with email system

### Changed
- **Security Improvements**
  - Updated jQuery to v3.7.1 to patch XSS vulnerabilities (CVE-2020-11023, CVE-2020-11022)
  - Enhanced security headers validation
  - Improved input sanitization across all forms
- **Deployment Modernization**
  - Systemd Quadlets support for production deployment
  - Native systemd integration with automatic startup
  - Improved Docker/Podman Compose setup
  - Deprecated native installation in favor of containerization

### Fixed
- Resolved jQuery security vulnerabilities
- Improved error handling in email transport
- Enhanced session management for better security

## [2.0.0] - 2024-06-01

### Added
- **Containerization Support**
  - Docker and Podman support with compose files
  - Systemd Quadlets for production deployment
  - Automated container build and deployment scripts
- **Comprehensive Testing Framework**
  - Playwright end-to-end testing integration
  - Automated UI testing for both script and noscript modes
  - Security headers validation testing
  - Responsive design testing
  - Mock server for isolated testing
- **Enhanced Documentation**
  - Comprehensive testing documentation (TESTING.md)
  - Docker deployment guide (DOCKER.md)
  - Quadlets deployment guide (QUADLETS.md)
  - Security best practices (SECURITY.md)
  - Contributing guidelines (CONTRIBUTING.md)

### Changed
- Improved installation process with multiple deployment options
- Enhanced error handling and logging
- Better session management and cleanup
- Modernized development workflow

### Deprecated
- Native installation scripts (install.sh, uninstall.sh) in favor of containerization

## [1.5.0] - 2023-12-01

### Added
- **Review System**
  - User rating and review functionality
  - Review cleanup and management
  - Statistics and analytics for reviews
- **Enhanced Chat Features**
  - Improved message cleanup (3-minute expiry)
  - Better randomized username generation
  - Enhanced color coding for users
- **Security Enhancements**
  - Improved header security
  - Better session isolation
  - Enhanced Tor integration

### Changed
- Optimized memory usage for chat storage
- Improved cleanup routines for better performance
- Enhanced error handling and user feedback

## [1.0.0] - 2017-11-01

### Added
- **Core Chat System**
  - Ephemeral hidden service creation via Tor
  - Anonymous chat functionality
  - No-disk storage policy (everything in memory)
  - Randomized usernames for enhanced privacy
  - Support for both JavaScript and no-JavaScript modes
- **Tor Integration**
  - Automatic hidden service generation
  - Encrypted communication through Tor network
  - Attribution-resistant chat environment
- **Basic Security Features**
  - No configuration required
  - Low barrier to entry
  - Minimal dependencies
  - No client installation needed
  - Automatic chat deletion
- **Dual Mode Support**
  - JavaScript-enabled mode for enhanced UX
  - NoScript mode for maximum security
  - Automatic detection and redirection

### Security
- All communications encrypted through Tor network
- No persistent storage of chat data
- Ephemeral service addresses for each session
- No user tracking or logging

---

## Release Notes

### Version 3.0.0 - Major Email System Release
This release transforms opsechat from a simple anonymous chat tool into a comprehensive secure communication platform. The addition of real email capabilities, burner email management, and automated domain rotation makes it suitable for security research, penetration testing, and privacy-focused communications.

### Version 2.0.0 - Modernization Release  
This release modernizes the deployment and testing infrastructure, making opsechat production-ready with containerization support and comprehensive automated testing.

### Version 1.5.0 - Feature Enhancement Release
Added user feedback capabilities and enhanced the core chat experience with better cleanup and management features.

### Version 1.0.0 - Initial Release
The foundational release establishing opsechat as a secure, anonymous chat platform built on Tor hidden services.

---

For more information about any release, please see the [README.md](README.md) and related documentation files.