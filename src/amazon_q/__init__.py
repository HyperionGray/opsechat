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
    Lazily import heavy modules so utility submodules can be used
    without requiring full AWS review dependencies at import time.
    """
    if name == 'AmazonQReviewer':
        from .reviewer import AmazonQReviewer
        return AmazonQReviewer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
