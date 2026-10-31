import sys
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_cards import (
    language_shares,
    languages_card,
    stats_card,
    streak_card,
    streaks,
)

TODAY = date(2026, 10, 31)


def history(*counts):
    """Build a {date: count} mapping ending today, oldest first."""
    return {
        TODAY - timedelta(days=len(counts) - 1 - i): c for i, c in enumerate(counts)
    }


def repository(*languages):
    return {
        "languages": {
            "edges": [
                {"size": size, "node": {"name": name, "color": colour}}
                for name, colour, size in languages
            ]
        }
    }


def test_current_streak_counts_back_from_today():
    assert streaks(history(1, 0, 2, 3), TODAY) == (2, 2)


def test_an_empty_today_does_not_end_the_streak():
    assert streaks(history(1, 1, 1, 0), TODAY)[0] == 3


def test_two_empty_days_end_the_streak():
    assert streaks(history(1, 1, 0, 0), TODAY)[0] == 0


def test_longest_streak_can_be_in_the_past():
    assert streaks(history(1, 1, 1, 1, 0, 1), TODAY) == (1, 4)


def test_no_contributions_gives_zero():
    assert streaks({}, TODAY) == (0, 0)


def test_languages_are_combined_across_repositories():
    shares = language_shares(
        [
            repository(("Python", "#111111", 300)),
            repository(("Python", "#111111", 100), ("C++", "#222222", 100)),
        ]
    )

    assert shares == [("Python", "#111111", 80.0), ("C++", "#222222", 20.0)]


def test_only_the_largest_languages_are_kept():
    repo = repository(*((f"L{i}", "#111111", 100 - i) for i in range(9)))

    assert len(language_shares([repo], limit=6)) == 6


def test_a_language_without_a_colour_still_gets_one():
    assert language_shares([repository(("Odd", None, 10))])[0][1]


def test_cards_are_valid_svg_and_escape_names():
    shares = [("C++ & friends", "#111111", 60.0), ("Python", "#222222", 40.0)]

    for svg in (
        stats_card([("Commits", 1200)]),
        languages_card(shares),
        streak_card(10, 2, 5),
    ):
        assert ElementTree.fromstring(svg).tag.endswith("svg")


def test_numbers_are_grouped_for_reading():
    assert "1,200" in stats_card([("Commits", 1200)])


def test_cards_given_the_same_height_are_the_same_size():
    rows = [("Commits", 1200), ("Followers", 5)]
    shares = [(f"L{i}", "#111111", 10.0) for i in range(6)]

    stats = ElementTree.fromstring(stats_card(rows, 168))
    languages = ElementTree.fromstring(languages_card(shares, 168))

    assert stats.attrib["width"] == languages.attrib["width"]
    assert stats.attrib["height"] == languages.attrib["height"] == "168"


def test_a_card_never_shrinks_below_its_content():
    rows = [("Row", i + 1) for i in range(6)]

    assert ElementTree.fromstring(stats_card(rows, 100)).attrib["height"] == "226"


def test_notebooks_do_not_count_towards_languages():
    shares = language_shares(
        [repository(("Jupyter Notebook", "#111111", 900), ("Python", "#222222", 100))]
    )

    assert shares == [("Python", "#222222", 100.0)]
