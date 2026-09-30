"""
This package provides various script utilities for managing and working with Python projects.

The scripts include functions for code linting, formatting, building docs, and running tests.
"""

__version__ = "0.1.0"

from .code_quality import lint, format

__all__ = [
    "lint",
    "format",
]
