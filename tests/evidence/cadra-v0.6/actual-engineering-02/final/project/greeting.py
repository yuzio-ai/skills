"""Greeting service using the shared prefix."""

from prefix import greeting_prefix


def greet(name: str) -> str:
    """Trim surrounding whitespace, using world when the result is empty."""
    trimmed_name = name.strip()
    return f"{greeting_prefix()}, {trimmed_name or 'world'}!"
