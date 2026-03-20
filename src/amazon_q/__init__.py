"""
Amazon Q Code Review Integration Package.

This package provides integration with Amazon Q Developer services for automated
code review, security scanning, and best practices analysis.
"""

__all__ = ['AmazonQReviewer']


def __getattr__(name):
    """Lazily load heavy reviewer dependencies on first access."""
    if name == 'AmazonQReviewer':
        from .reviewer import AmazonQReviewer
        return AmazonQReviewer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
