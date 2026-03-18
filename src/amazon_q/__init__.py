"""
Amazon Q Code Review Integration Package

This package provides integration with Amazon Q Developer services for automated
code review, security scanning, and best practices analysis.

Main exports:
    - AmazonQReviewer: Main reviewer class
"""

__all__ = ['AmazonQReviewer']


def __getattr__(name):
    """
    Lazily load heavy reviewer dependencies.

    This allows importing submodules such as security/quality/architecture analyzers
    in environments where optional AWS SDK dependencies are not installed.
    """
    if name == 'AmazonQReviewer':
        from .reviewer import AmazonQReviewer
        return AmazonQReviewer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
