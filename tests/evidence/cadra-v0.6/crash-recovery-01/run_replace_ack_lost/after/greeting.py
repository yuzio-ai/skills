"""Greeting service using the shared prefix."""

from prefix import greeting_prefix


def greet(name: str) -> str:
    """Preserve a nonempty name, using world only for an empty string."""
    return f"{greeting_prefix()}, {name if name else 'world'}!"
