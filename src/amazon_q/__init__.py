"""
Amazon Q Code Review Integration Package

This package provides integration with Amazon Q Developer services for automated
code review, security scanning, and best practices analysis.

Main exports:
    - AmazonQReviewer: Main reviewer class
"""

def __getattr__(name):
    """
    Lazily import heavy modules so local heuristic analyzers can be used
    without requiring optional AWS dependencies at import time.
    """
    if name == 'AmazonQReviewer':
        from .reviewer import AmazonQReviewer
        return AmazonQReviewer
    raise AttributeError(f"module 'amazon_q' has no attribute {name!r}")

__all__ = ['AmazonQReviewer']
