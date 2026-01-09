"""URL utilities for extracting and cleaning Granola links."""

import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

# Pattern to match ANY Granola URL
# Matches: https://notes.granola.ai/... (any path)
GRANOLA_URL_PATTERN = re.compile(
    r"https?://notes\.granola\.ai/[^\s<>\"']+"
)


def extract_granola_url(text: str) -> Optional[str]:
    """Extract the first Granola URL from the given text.

    Args:
        text: The text to search for Granola URLs.

    Returns:
        The first matching Granola URL, or None if no match found.
    """
    match = GRANOLA_URL_PATTERN.search(text)
    return match.group(0) if match else None


def clean_url(url: str) -> str:
    """Remove query parameters and fragments from a URL.

    Args:
        url: The URL to clean.

    Returns:
        The URL with query parameters and fragments removed.

    Example:
        >>> clean_url("https://notes.granola.ai/d/abc123?utm_source=slack")
        "https://notes.granola.ai/d/abc123"
    """
    parsed = urlparse(url)
    # Reconstruct URL without query string or fragment
    cleaned = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        "",  # params (rarely used)
        "",  # query
        "",  # fragment
    ))
    return cleaned


def contains_granola_url(text: str) -> bool:
    """Check if the text contains a Granola URL.

    Args:
        text: The text to search.

    Returns:
        True if a Granola URL is found, False otherwise.
    """
    return GRANOLA_URL_PATTERN.search(text) is not None
