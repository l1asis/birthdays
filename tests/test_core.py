import datetime
from dataclasses import asdict

import pytest

from birthdays import birthdays
from birthdays.birthdays import BirthdayEntry, day_might_exist, leapling_safe_date


@pytest.mark.parametrize(
    ("year", "system", "expected"),
    [
        (2024, "before", datetime.date(2024, 2, 29)),
        (2024, "after", datetime.date(2024, 2, 29)),
        (2025, "before", datetime.date(2025, 2, 28)),
        (2025, "after", datetime.date(2025, 3, 1)),
        (1900, "before", datetime.date(1900, 2, 28)),
        (1900, "after", datetime.date(1900, 3, 1)),
        (2000, "before", datetime.date(2000, 2, 29)),
        (2000, "after", datetime.date(2000, 2, 29)),
    ],
)
def test_leapling_safe_date_obeys_leap_year_and_observation_policy(
    year, system, expected
):
    assert leapling_safe_date(year, 2, 29, system) == expected


def test_leapling_safe_date_preserves_ordinary_dates():
    assert leapling_safe_date(2025, 5, 12) == datetime.date(2025, 5, 12)


def test_leapling_safe_date_rejects_other_invalid_dates():
    with pytest.raises(ValueError):
        leapling_safe_date(2025, 4, 31)


@pytest.mark.parametrize(
    ("year", "month", "day", "expected"),
    [
        (None, 2, 29, True),
        (2024, 2, 29, True),
        (2025, 2, 29, False),
        (1900, 2, 29, False),
        (2000, 2, 29, True),
        (None, 4, 31, False),
        (2025, 1, 0, False),
        (2025, 1, 32, False),
        (2025, 1, 31, True),
    ],
)
def test_day_might_exist_handles_unknown_years_and_month_boundaries(
    year, month, day, expected
):
    assert day_might_exist(year, month, day) is expected


@pytest.mark.parametrize("existing_year", [None, 1980])
def test_noninteractive_merge_preserves_identity_and_combines_metadata(
    monkeypatch, existing_year
):
    existing = BirthdayEntry(
        "old-id",
        "Example Person",
        5,
        12,
        year=existing_year,
        notes=" First note ",
        groups=["Friends"],
        name_parts={"first": "Example"},
    )
    incoming = BirthdayEntry(
        "new-id",
        "Example Person",
        6,
        15,
        year=1990,
        notes=" Second note ",
        groups=["friends", "Work"],
        leap_system="after",
        name_parts={"last": "Person"},
    )
    before = (asdict(existing), asdict(incoming))

    def unexpected_prompt(*args, **kwargs):
        raise AssertionError("noninteractive merge must not prompt")

    monkeypatch.setattr(birthdays, "confirm", unexpected_prompt)
    monkeypatch.setattr(birthdays, "choose", unexpected_prompt)
    merged = birthdays.merge_pair(existing, incoming, interactive=False)

    assert merged.id == "old-id"
    assert merged.full_name == "Example Person"
    assert (merged.month, merged.day) == (6, 15)
    assert merged.year == (1990 if existing_year is None else existing_year)
    assert merged.notes == "First note; Second note"
    assert merged.groups == ["friends", "work"]
    assert merged.name_parts == {"first": "Example", "last": "Person"}
    assert merged.leap_system == "after"
    assert (asdict(existing), asdict(incoming)) == before


def test_next_occurrence_includes_today_and_rolls_over_at_year_end():
    entry = BirthdayEntry("example-id", "Example Person", 12, 31)
    assert entry.get_next_occurrence(datetime.date(2025, 12, 31)) == datetime.date(
        2025, 12, 31
    )
    assert entry.get_next_occurrence(datetime.date(2026, 1, 1)) == datetime.date(
        2026, 12, 31
    )
