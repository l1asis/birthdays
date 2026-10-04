import pytest
from icalendar import Calendar

from birthdays.birthdays import BirthdayEntry, build_ical


@pytest.mark.parametrize("years", [0, 1, 3])
@pytest.mark.parametrize("birth_year", [None, 1990])
def test_exported_birthdays_do_not_block_calendar_availability(years, birth_year):
    entry = BirthdayEntry(
        id="synthetic-contact",
        full_name="Example Person",
        month=5,
        day=12,
        year=birth_year,
    )
    calendar = build_ical(
        [entry],
        years=years,
        alarm_days=1,
        alarm_time="09:00",
        title_tmpl="{name}'s birthday",
        desc_tmpl="Turns {age}",
        desc_fallback_tmpl="Birthday",
        alarm_desc_tmpl="Wish {name} a happy birthday",
    )

    serialized = calendar.to_ical()
    events = Calendar.from_ical(serialized).walk("VEVENT")
    assert len(events) == (years or 1)
    for event in events:
        assert str(event["TRANSP"]) == "TRANSPARENT"
        assert event.decoded("DTSTART").month == 5
        assert event.decoded("DTSTART").day == 12
        assert event["SUMMARY"] == "Example Person's birthday"
        assert len(event.walk("VALARM")) == 1
        assert event["UID"].startswith("synthetic-contact")
    assert ("RRULE" in events[0]) is (years == 0)
