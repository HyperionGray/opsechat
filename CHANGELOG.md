# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Complete CI/CD review workflow integration
- Amazon Q code review automation
- Comprehensive documentation review system

## [2.1.0] - 2024-12-11

### Added
- **Real Email System Integration** - Full SMTP/IMAP support for sending and receiving actual emails
- **Modern Burner Email System** - Guerrillamail-style rotating anonymous email addresses with:
  - Multi-burner management with live countdown timers
  - Quick rotation and instant copy functionality
  - Smart stats dashboard for tracking active burners
- **Automated Domain Purchasing** - Porkbun API integration for cheap domain rotation (.xyz, .club, etc.)
- **Budget Management** - Configurable monthly spending limits for domain purchases
- **Email Security Tools** - Spoofing detection, phishing simulation, and security research capabilities
- **PGP Encryption Support** - End-to-end encryption for both chat and email systems
- **Raw Mode Email Editing** - Full control over email headers for security testing
- **Containerization Support** - Docker and Podman deployment options
- **Systemd Quadlets** - Native systemd integration for production deployments

### Security
- **jQuery Security Update** - Updated to v3.7.1 to patch XSS vulnerabilities (CVE-2020-11023, CVE-2020-11022)
- **Enhanced Security Headers** - Comprehensive security header validation
- **Plain Text Email Processing** - HTML and images shown as text for security analysis
- **Responsible Disclosure Framework** - Structured security reporting process

### Changed
- **Deprecated Native Installation** - Container/quadlet deployment now recommended
- **Enhanced Testing Suite** - Comprehensive Playwright E2E tests covering all functionality
- **Improved Documentation** - Extensive documentation for all features and deployment methods
- **Modernized Architecture** - Modular design with separate email, domain, and security components

### Fixed
- **Memory Management** - Improved in-memory storage for chat and email data
- **Tor Integration** - Enhanced ephemeral hidden service creation and management
- **Session Handling** - Better session management and cleanup
- **Cross-browser Compatibility** - Improved support for Tor Browser and noscript environments

## [2.0.0] - 2024-06-15

### Added
- **Email System Foundation** - Initial email functionality with basic SMTP support
- **PGP Integration** - Basic PGP encryption and decryption capabilities
- **Enhanced Chat Features** - Improved chat system with better user experience
- **Security Improvements** - Enhanced security measures and vulnerability fixes

### Changed
- **Major Architecture Refactor** - Modular design for better maintainability
- **Improved User Interface** - Better responsive design and accessibility
- **Enhanced Documentation** - Comprehensive guides and examples

## [1.5.0] - 2023-12-01

### Added
- **Containerization** - Docker and Podman support for easy deployment
- **Automated Testing** - Playwright test suite for comprehensive E2E testing
- **Enhanced Security** - Additional security headers and protections

### Changed
- **Improved Installation** - Streamlined installation process with multiple options
- **Better Error Handling** - Enhanced error reporting and user feedback

## [1.0.0] - 2023-06-01

### Added
- **Core Chat System** - Anonymous chat via Tor hidden services
- **Ephemeral Services** - Temporary chat rooms with automatic cleanup
- **No-JavaScript Support** - Full functionality without JavaScript
- **Randomized Usernames** - Automatic username generation for anonymity
- **In-Memory Storage** - No data persistence for enhanced privacy
- **Tor Integration** - Native Tor hidden service creation and management

### Security
- **End-to-End Encryption** - All communications encrypted via Tor
- **No Disk Storage** - Everything stored in memory only
- **Anonymous Architecture** - No user tracking or identification
- **Secure Defaults** - Security-first configuration out of the box

## [0.9.0] - 2022-12-01

### Added
- **Initial Release** - Basic anonymous chat functionality
- **Tor Hidden Services** - Ephemeral hidden service creation
- **Flask Web Interface** - Simple web-based chat interface
- **Basic Security** - Fundamental security measures

---

## Release Notes

### Version 2.1.0 Highlights
This major release transforms opsechat from a simple anonymous chat tool into a comprehensive secure communication platform. The addition of real email capabilities, automated domain rotation, and advanced security testing tools makes it suitable for security research, penetration testing, and privacy-focused communication.

### Version 2.0.0 Highlights  
The 2.0 release introduced the email system foundation and PGP integration, marking the evolution from chat-only to a multi-modal secure communication platform.

### Version 1.0.0 Highlights
The first stable release established the core anonymous chat functionality that remains the foundation of the project, with robust Tor integration and privacy-first design principles.

---

For detailed information about any release, see the corresponding documentation files and commit history in the repository.