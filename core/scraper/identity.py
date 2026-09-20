"""
Identity signals: what actually proves a profile belongs to the same person.

Nothing here guesses. A row is written only when the platform proved the profile
exists, and its confidence is the sum of the weights of the signals that were
observed - see SIGNAL_WEIGHTS in core.constants for the numbers and the README for
what each one means.
"""

from collections.abc import Iterable
from typing import TypedDict
from urllib.parse import urlsplit

from core.constants import SIGNAL_WEIGHTS, Signal
from core.scraper.platforms import GENERIC_NOT_FOUND_MARKERS, PlatformSpec


class KnownProfiles(TypedDict):
    """What the target's confirmed rows already prove about the person."""

    handles: set[str]
    names: set[str]
    urls: set[str]


class CandidateFacts(TypedDict):
    """What one probe observed about a candidate."""

    username: str
    display_name: str
    bio_urls: Iterable[str]
    from_bio: bool


def canonical_url(url: str) -> str:
    """Host and path, lowercased without a trailing slash, for comparisons."""
    parts = urlsplit(url)
    return f"{parts.netloc.lower()}{parts.path.rstrip('/').lower()}"


def profile_exists(
    requested_url: str,
    final_url: str,
    content: str,
    platform: PlatformSpec,
) -> bool:
    """Whether the platform proved a profile exists at the requested URL."""
    if canonical_url(requested_url) != canonical_url(final_url):
        return False

    markers = platform.get("not_found_markers") or GENERIC_NOT_FOUND_MARKERS
    lowered = content.lower()
    return not any(marker in lowered for marker in markers)


def signals_for(facts: CandidateFacts, known: KnownProfiles) -> list[str]:
    """List the signals that fired for a confirmed candidate, in a stable order."""
    fired = [Signal.EXISTENCE_PROVEN]

    if facts["username"].lower() in known["handles"]:
        fired.append(Signal.HANDLE_MATCHES_SEED)

    display_name = facts["display_name"].lower()
    if display_name and display_name in known["names"]:
        fired.append(Signal.DISPLAY_NAME_MATCHES_KNOWN)

    linked = {canonical_url(url) for url in facts["bio_urls"]}
    if known["urls"] & linked:
        fired.append(Signal.BIO_LINKS_TO_CONFIRMED)

    if facts["from_bio"]:
        fired.append(Signal.PROBED_FROM_CONFIRMED_BIO)

    return fired


def confidence_for(signals: Iterable[str]) -> float:
    """Sum the documented weights of the signals that fired."""
    total = sum(SIGNAL_WEIGHTS.get(signal, 0.0) for signal in signals)
    return round(total, 2)
