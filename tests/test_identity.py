from core.constants import Signal
from core.scraper.identity import (
    KnownProfiles,
    canonical_url,
    confidence_for,
    profile_exists,
    signals_for,
)
from core.scraper.platforms import GENERIC_NOT_FOUND_MARKERS, PlatformSpec

PLATFORM: PlatformSpec = {
    "name": "github",
    "url": "https://github.com/{username}",
    "bio_selector": None,
}

PLATFORM_WITH_MARKERS: PlatformSpec = {
    **PLATFORM,
    "not_found_markers": ("gone fishing",),
}

NOTHING_KNOWN: KnownProfiles = {"handles": set(), "names": set(), "urls": set()}


def _facts(**overrides) -> dict:
    facts = {
        "username": "someone",
        "display_name": "Someone",
        "bio_urls": [],
        "from_bio": False,
    }
    facts.update(overrides)
    return facts


def test_canonical_url_ignores_case_trailing_slash_and_query():
    assert (
        canonical_url("HTTPS://GitHub.com/Seed_User/?tab=1") == "github.com/seed_user"
    )


def test_a_clean_200_proves_existence():
    assert profile_exists(
        "https://github.com/seed_user",
        "https://github.com/seed_user/",
        "<html>profile</html>",
        PLATFORM,
    )


def test_a_redirect_away_from_the_profile_proves_nothing():
    assert not profile_exists(
        "https://github.com/seed_user",
        "https://github.com/",
        "<html>welcome</html>",
        PLATFORM,
    )


def test_generic_markers_flag_a_not_found_page():
    html = f"<html>{GENERIC_NOT_FOUND_MARKERS[0]}</html>"

    assert not profile_exists(
        "https://github.com/seed_user",
        "https://github.com/seed_user",
        html,
        PLATFORM,
    )


def test_platform_markers_replace_the_generic_ones():
    url = "https://x.com/seed_user"

    assert not profile_exists(
        url, url, "<html>gone fishing</html>", PLATFORM_WITH_MARKERS
    )
    assert profile_exists(
        url, url, "<html>page not found</html>", PLATFORM_WITH_MARKERS
    )


def test_only_existence_fires_when_nothing_is_corroborated():
    fired = signals_for(_facts(), NOTHING_KNOWN)

    assert fired == [Signal.EXISTENCE_PROVEN]
    assert confidence_for(fired) == 0.0


def test_a_matching_handle_carries_its_weight():
    known: KnownProfiles = {
        "handles": {"seed_user"},
        "names": set(),
        "urls": set(),
    }

    fired = signals_for(_facts(username="seed_user"), known)

    assert fired == [Signal.EXISTENCE_PROVEN, Signal.HANDLE_MATCHES_SEED]
    assert confidence_for(fired) == 0.4


def test_a_matching_display_name_carries_its_weight():
    known: KnownProfiles = {
        "handles": set(),
        "names": {"seed user"},
        "urls": set(),
    }

    fired = signals_for(_facts(display_name="Seed User"), known)

    assert Signal.DISPLAY_NAME_MATCHES_KNOWN in fired
    assert confidence_for(fired) == 0.3


def test_a_bio_link_to_a_confirmed_profile_carries_its_weight():
    known: KnownProfiles = {
        "handles": set(),
        "names": set(),
        "urls": {"github.com/seed_user"},
    }

    fired = signals_for(
        _facts(bio_urls=["https://github.com/seed_user"]),
        known,
    )

    assert Signal.BIO_LINKS_TO_CONFIRMED in fired
    assert confidence_for(fired) == 0.2


def test_coming_from_a_bio_carries_its_weight():
    fired = signals_for(_facts(from_bio=True), NOTHING_KNOWN)

    assert fired == [Signal.EXISTENCE_PROVEN, Signal.PROBED_FROM_CONFIRMED_BIO]
    assert confidence_for(fired) == 0.1


def test_every_signal_together_reaches_full_confidence():
    known: KnownProfiles = {
        "handles": {"seed_user"},
        "names": {"seed user"},
        "urls": {"github.com/seed_user"},
    }

    fired = signals_for(
        _facts(
            username="seed_user",
            display_name="Seed User",
            bio_urls=["https://github.com/seed_user"],
            from_bio=True,
        ),
        known,
    )

    assert confidence_for(fired) == 1.0


def test_an_unknown_signal_weighs_nothing():
    assert confidence_for(["existence_proven", "made_up"]) == 0.0
