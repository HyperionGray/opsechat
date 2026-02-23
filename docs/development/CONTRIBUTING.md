# Contributing to opsechat

Thank you for considering contributing to opsechat! This document provides guidelines for contributing to this project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.

## How to Contribute

### Reporting Issues

- Check if the issue already exists in the [issue tracker](https://github.com/HyperionGray/opsechat/issues)
- Use a clear and descriptive title
- Provide detailed steps to reproduce the issue
- Include relevant logs, screenshots, or error messages
- Specify your environment (OS, Python version, Tor version, etc.)

### Proposing Changes

1. **Fork the repository** and create a new branch from `master`
2. **Make your changes** with clear, focused commits
3. **Test thoroughly** - ensure your changes don't break existing functionality
4. **Update documentation** if needed
5. **Submit a pull request** with a clear description of your changes

### Pull Request Guidelines

- Keep changes focused and atomic
- Write clear commit messages
- Include tests for new features
- Update documentation to reflect changes
- Ensure all tests pass before submitting
- Follow the existing code style

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Tor
- Git

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/HyperionGray/opsechat.git
   cd opsechat
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python runserver.py
   ```

4. Run tests:
   ```bash
   npm test  # for Playwright E2E tests
   ```

## Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused and modular

## Testing

- Write tests for new features
- Ensure existing tests pass
- Test in Tor Browser when making UI changes
- Test security-critical features thoroughly

## Security Considerations

This is a security-focused project. When contributing:

- **Never commit secrets or credentials**
- **Review security implications** of your changes
- **Test for common vulnerabilities** (XSS, CSRF, injection attacks)
- **Report security issues privately** to the maintainers
- **Use secure coding practices**
- **Minimize data retention** and logging
- **Preserve anonymity features**

## Documentation

- Update README.md for user-facing changes
- Add inline documentation for complex code
- Update relevant .md files in the repository
- Include examples where helpful

## Questions?

If you have questions about contributing, feel free to:
- Open an issue for discussion
- Review existing issues and pull requests
- Check the documentation in the repository

Thank you for helping make opsechat better and more secure!
