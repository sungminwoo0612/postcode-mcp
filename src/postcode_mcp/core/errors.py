from __future__ import annotations


class PostcodeError(Exception):
    """Base error for postcode-mcp."""


class UpstreamError(PostcodeError):
    """Raised when an upstream API falls."""


class ValidationError(PostcodeError):
    """Raised when input validation fails."""
