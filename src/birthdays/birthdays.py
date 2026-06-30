import argparse
import base64
import calendar
import datetime
import difflib
import json
import os
import quopri
import re
import sys
import uuid
from collections import defaultdict
from collections.abc import Collection
from dataclasses import asdict, dataclass
from operator import attrgetter
from pathlib import Path
from typing import Any, List, Literal, Optional, overload

from dateutil.relativedelta import relativedelta
from emojis import date_to_emoji
from platformdirs import user_data_path

VCARD = re.compile(r"BEGIN:VCARD.*?END:VCARD", flags=re.DOTALL | re.IGNORECASE)
FULL_NAME = re.compile(r"^FN(;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)
BIRTHDAY = re.compile(r"^BDAY(?:;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)
DATE = re.compile(r"^(\d{4}|--)?-?(0[1-9]|1[0-2])-?(0[1-9]|[12]\d|3[01])$")
NOTE = re.compile(r"^NOTE(;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)
UNFOLD = re.compile(r"\r?\n[ \t]")  # glues lines that start with a space or tab
UNFOLD_SOFT = re.compile(r"=\r?\n")  # glues lines that end with an '='

# ==========================================
#               DATA MODELS
# ==========================================


@dataclass
class BirthdayEntry:
    """A single birthday entry in the database."""

    id: str
    full_name: str
    month: int
    day: int
    year: Optional[int] = None
    notes: Optional[str] = None
    leap_system: Literal["after", "before"] = "before"

    def get_age(self) -> int | None:
        """Return the person's current age, or None if the year is unknown."""
        if self.year is None:
            return None
        today = datetime.date.today()
        this_year = leapling_safe_date(
            today.year, self.month, self.day, self.leap_system
        )
        had_birthday = today >= this_year
        return today.year - self.year - (0 if had_birthday else 1)

    def is_today(self) -> bool:
        """Check if today is the person's birthday."""
        today = datetime.date.today()
        this_year = leapling_safe_date(
            today.year, self.month, self.day, self.leap_system
        )
        return this_year.month == today.month and this_year.day == today.day

    def get_next_occurrence(self, from_date: datetime.date) -> datetime.date:
        """Calculate the exact date of the next birthday."""
        this_year = leapling_safe_date(
            from_date.year, self.month, self.day, self.leap_system
        )
        if from_date.month < this_year.month or (
            from_date.month == this_year.month and from_date.day < this_year.day
        ):
            return this_year
        return leapling_safe_date(
            from_date.year + 1, self.month, self.day, self.leap_system
        )

    def get_prev_occurrence(self, from_date: datetime.date) -> datetime.date:
        """Calculate the exact date of the previous birthday."""
        this_year = leapling_safe_date(
            from_date.year, self.month, self.day, self.leap_system
        )
        if from_date.month < this_year.month or (
            from_date.month == this_year.month and from_date.day < this_year.day
        ):
            return leapling_safe_date(
                from_date.year - 1, self.month, self.day, self.leap_system
            )
        return this_year

    def next_occurrence_in(self, from_date: datetime.date) -> relativedelta:
        """Calculate the exact distance to the next birthday."""
        return relativedelta(self.get_next_occurrence(from_date), from_date)

    def prev_occurrence_in(self, from_date: datetime.date) -> relativedelta:
        """Calculate the exact distance to the previous birthday."""
        return relativedelta(self.get_prev_occurrence(from_date), from_date)

    def __post_init__(self):
        if not day_might_exist(self.year, self.month, self.day):
            raise ValueError(
                f"Date is out of range. "
                f"Got: {f'{self.year}-' if self.year is not None else ''}"
                f"{self.month}-{self.day}"
            )

    def __str__(self) -> str:
        year_str = f"{self.year}-" if self.year else ""
        date_str = f"{year_str}{self.month:02d}-{self.day:02d}"

        base = f"{self.full_name} ({date_str})"
        if self.notes:
            base = f"{base} - {self.notes}"
        return base

    def __repr__(self) -> str:
        return (
            f"BirthdayEntry({repr(self.id)}, "
            f"{repr(self.full_name)}, "
            f"{self.month}, "
            f"{self.day}, "
            f"{self.year}, "
            f"{repr(self.notes) if self.notes else 'None'})"
        )

    def __lt__(self, other: "BirthdayEntry | datetime.date") -> bool:
        if self.year is not None and other.year is not None:
            if self.year != other.year:
                return self.year < other.year
        return self.month < other.month or (
            self.month == other.month and self.day < other.day
        )

    def __gt__(self, other: "BirthdayEntry | datetime.date") -> bool:
        if self.year is not None and other.year is not None:
            if self.year != other.year:
                return self.year > other.year
        return self.month > other.month or (
            self.month == other.month and self.day > other.day
        )

    def __le__(self, other: "BirthdayEntry | datetime.date") -> bool:
        if self.year is not None and other.year is not None:
            if self.year != other.year:
                return self.year < other.year
        return self.month < other.month or (
            self.month == other.month and self.day <= other.day
        )

    def __ge__(self, other: "BirthdayEntry | datetime.date") -> bool:
        if self.year is not None and other.year is not None:
            if self.year != other.year:
                return self.year > other.year
        return self.month > other.month or (
            self.month == other.month and self.day >= other.day
        )


# ==========================================
#               STORAGE APIs
# ==========================================


def get_database_path() -> Path:
    """Resolve OS-specific config path."""
    if custom_path := os.getenv("BIRTHDAYS_HOME"):
        path = Path(custom_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # TODO: Replace with __init__.py variable:
    return user_data_path(
        "birthdays",
        "Volodymyr Horshenin (@l1asis)",
        ensure_exists=True,
    )


def as_birthday_entry(dictionary: dict[str, Any]) -> BirthdayEntry:
    """Read a JSON dictionary and safely convert it into BirthdayEntry."""
    return BirthdayEntry(
        dictionary["id"],
        dictionary["full_name"],
        dictionary["month"],
        dictionary["day"],
        dictionary.get("year"),
        dictionary.get("notes"),
        dictionary.get("leap_system", "before"),
    )


def load_database(db_path: Path) -> List[BirthdayEntry]:
    """Read the JSON file and inflate it into BirthdayEntry objects."""
    if not db_path.exists():
        return []

    with open(db_path, "r", encoding="utf-8") as file:
        return json.load(file, object_hook=as_birthday_entry)


def save_database(entries: List[BirthdayEntry], db_path: Path) -> None:
    """Serialize BirthdayEntry objects and write them to the JSON file."""
    dictionaries = tuple(asdict(entry) for entry in entries)
    with open(db_path, "w", encoding="utf-8") as file:
        json.dump(dictionaries, file, indent=4)


# ==========================================
#            CORE LOGIC APIs
# ==========================================


def leapling_safe_date(
    year: int, month: int, day: int, leap_system: Literal["after", "before"] = "before"
) -> datetime.date:
    if not is_leap(year) and month == 2 and day == 29:
        if leap_system == "before":
            return datetime.date(year, 2, 28)
        return datetime.date(year, 3, 1)
    return datetime.date(year, month, day)


def is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def day_might_exist(year: int | None, month: int, day: int) -> bool:
    """Check if a day is valid for a given month, handling missing years safely."""
    _, num_days = calendar.monthrange(year if year is not None else 2024, month)
    return 1 <= day <= num_days


def parse_vcards(
    vcf_file: Path, leap_system: Literal["after", "before"]
) -> List[BirthdayEntry]:
    """Extract names and birthdays from all vCard formats."""
    with open(vcf_file, "r", encoding="utf-8") as file:
        vcards: list[str] = VCARD.findall(file.read())

    birthdays: List[BirthdayEntry] = []

    for vcard in vcards:
        fn_match = FULL_NAME.search(vcard)
        bday_match = BIRTHDAY.search(vcard)

        if fn_match is not None:
            parameters = fn_match.group(1)
            full_name = fn_match.group(2)

            if parameters:
                if "ENCODING=QUOTED-PRINTABLE" in parameters:
                    unquoted = quopri.decodestring(full_name)
                    if "CHARSET=UTF-8" in parameters:
                        full_name = unquoted.decode("utf-8")
                elif "ENCODING=b" in parameters:
                    unbased = base64.standard_b64decode(full_name)
                    if "CHARSET=UTF-8" in parameters:
                        full_name = unbased.decode("utf-8")

            if bday_match is not None:
                date_str = bday_match.group(1)
                year = month = day = None

                try:
                    date = datetime.date.fromisoformat(date_str)
                    year, month, day = date.year, date.month, date.day

                except ValueError:
                    date_match = DATE.match(date_str)

                    if date_match is not None:
                        year, month, day = (
                            int(year_match)
                            if (year_match := date_match.group(1)).isdecimal()
                            else None,
                            int(date_match.group(2)),
                            int(date_match.group(3)),
                        )

                if month is not None and day is not None:
                    birthdays.append(
                        BirthdayEntry(
                            uuid.uuid4().hex,
                            full_name,
                            month,
                            day,
                            year,
                            leap_system,
                        )
                    )

    return birthdays


def merge_pair(
    existing: BirthdayEntry, incoming: BirthdayEntry, interactive: bool = True
) -> BirthdayEntry:
    """Combine data of two entries meaningfully."""

    merged_notes = tuple(n for n in (existing.notes, incoming.notes) if n)
    merged_notes = "; ".join(merged_notes) if merged_notes else None

    if interactive:
        notes_choice = choose(("Existing", "Incoming", "Merge"))
        if notes_choice == "1":
            final_notes = existing.notes
        elif notes_choice == "2":
            final_notes = incoming.notes
        else:
            final_notes = merged_notes

        return BirthdayEntry(
            existing.id,
            incoming.full_name
            if existing.full_name != incoming.full_name
            and confirm(f"Change the full name?")
            else existing.full_name,
            incoming.month
            if existing.month != incoming.month and confirm(f"Change the month?")
            else existing.month,
            incoming.day
            if existing.day != incoming.day and confirm(f"Change the day?")
            else existing.day,
            incoming.year
            if existing.year is None
            or (existing.year != incoming.year and confirm(f"Change the year?"))
            else existing.year,
            final_notes,
            incoming.leap_system
            if existing.leap_system != incoming.leap_system
            and confirm(f"Change the leap system?")
            else existing.leap_system,
        )
    return BirthdayEntry(
        existing.id,
        incoming.full_name,
        incoming.month,
        incoming.day,
        incoming.year if existing.year is None else existing.year,
        merged_notes,
        incoming.leap_system,
    )


def merge_entries(
    existing: List[BirthdayEntry],
    incoming: List[BirthdayEntry],
    interactive: bool = True,
) -> List[BirthdayEntry]:
    """Merge two lists using fuzzy string matching to detect similar names."""

    existing_map: dict[str, list[BirthdayEntry]] = defaultdict(list)
    for entry in existing:
        existing_map[entry.full_name].append(entry)

    existing_names = tuple(existing_map.keys())

    final_db = {entry.id: entry for entry in existing}

    for new_entry in incoming:
        if new_entry.full_name in existing_map:
            if len(existing_map[new_entry.full_name]) > 1:
                choice = choose(
                    existing_map[new_entry.full_name],
                    prompt=f"\nMultiple exact matches for '{new_entry.full_name}'. Which one to merge into?",
                    extra={"S": "Skip this contact entirely"},
                    required=True,
                )

                if choice == "S":
                    continue

                match = existing_map[new_entry.full_name][int(choice) - 1]
            else:
                match = existing_map[new_entry.full_name][0]

            if (
                match.month == new_entry.month
                and match.day == new_entry.day
                and match.year == new_entry.year
                and match.notes == new_entry.notes
            ):
                continue

            if interactive:
                print(
                    f"\nExact name match found for '{new_entry.full_name}', but data differs."
                )
                print(f"Existing: {match}")
                print(f"Incoming: {new_entry}")
                if confirm("Update existing entry?"):
                    final_db[match.id] = merge_pair(match, new_entry)
            else:
                final_db[match.id] = merge_pair(match, new_entry, interactive=False)

        else:
            close_names = difflib.get_close_matches(
                new_entry.full_name, existing_names, n=3, cutoff=0.8
            )

            if not close_names:
                final_db[new_entry.id] = new_entry
                continue

            if interactive:
                print(f"\nIncoming contact: {new_entry}")
                print("Found similar existing names:")

                options: List[BirthdayEntry] = [
                    entry for name in close_names for entry in existing_map[name]
                ]

                choice = choose(
                    options,
                    extra={
                        "A": "Add as completely new entry",
                        "S": "Skip this contact entirely",
                    },
                    required=True,
                )

                if choice == "A":
                    final_db[new_entry.id] = new_entry
                elif choice == "S":
                    pass
                elif choice.isdigit():
                    selected_match = options[int(choice) - 1]
                    final_db[selected_match.id] = merge_pair(selected_match, new_entry)
            else:
                final_db[new_entry.id] = new_entry

    return list(final_db.values())


# ==========================================
#             PRESENTATION APIs
# ==========================================


def confirm(
    prompt: str = "Are you sure?",
    default_no: bool = True,
    required: bool = False,
    allow_skip: bool = False,
) -> bool | None:
    """Prompt user for a confirmation."""

    if required:
        suffix = "(y/n/s)" if allow_skip else "(y/n)"
    else:
        if allow_skip:
            suffix = "(y/N/s)" if default_no else "(Y/n/s)"
        else:
            suffix = "(y/N)" if default_no else "(Y/n)"

    while True:
        user_input = input(f"{prompt} {suffix}: ").strip().lower()

        if not user_input:
            if required:
                print("Input is required. Please choose an option.")
                continue
            return not default_no

        elif user_input in {"yes", "y"}:
            return True

        elif allow_skip and user_input in {"skip", "s"}:
            return None

        elif user_input in {"no", "n"}:
            return False

        if required:
            print("Invalid input. Please choose a valid option.")
            continue

        return False


@overload
def choose(
    options: Collection[Any],
    extra: dict[str, str] | None = None,
    prompt: str = "Choose an option:",
    start: int = 1,
    required: Literal[True] = True,
) -> str: ...


@overload
def choose(
    options: Collection[Any],
    extra: dict[str, str] | None = None,
    prompt: str = "Choose an option:",
    start: int = 1,
    required: Literal[False] = ...,
) -> str | None: ...


def choose(
    options: Collection[Any],
    extra: dict[str, str] | None = None,
    prompt: str = "Choose an option:",
    start: int = 1,
    required: bool = False,
) -> str | None:
    """Prompt user to make a choice."""
    print(prompt)
    for position, option in enumerate(options, start):
        print(f"[{position}] - {option}")

    if extra:
        for key, value in extra.items():
            print(f"[{key}] - {value}")

    while True:
        choice = input("-> My choice is... ").strip()

        if not choice:
            if required:
                print("Input is required. Please choose a valid option.")
                continue
            return None

        if choice.isdecimal():
            if start <= int(choice) < start + len(options):
                return choice

        if extra:
            choice_lower = choice.lower()
            for key in extra:
                if key.lower() == choice_lower:
                    return key

        if required:
            print("Invalid choice. Please try again.")
        else:
            return None


def to_ordinal(number: int) -> str:
    """Convert a cardinal number into its ordinal form."""
    n = abs(number)
    if n % 100 in (11, 12, 13):
        return f"{n}th"
    elif n % 10 == 1:
        return f"{n}st"
    elif n % 10 == 2:
        return f"{n}nd"
    elif n % 10 == 3:
        return f"{n}rd"
    return f"{n}th"


def display_birthdays(
    entries: List[BirthdayEntry],
    sort_by: Literal["name", "date", "upcoming", "recent", "age"] = "upcoming",
    sort_order: Literal["asc", "desc"] = "asc",
    view_style: Literal["simple", "table", "calendar"] = "simple",
) -> None:
    """Handle all terminal printing."""
    today = datetime.date.today()

    if sort_by == "name":
        entries.sort(
            key=lambda entry: entry.full_name.casefold(), reverse=sort_order == "desc"
        )
    elif sort_by == "date":
        entries.sort(
            key=lambda entry: (
                entry.year
                if entry.year is not None
                else float("inf" if sort_order == "asc" else "-inf"),
                entry.month,
                entry.day,
            ),
            reverse=sort_order == "desc",
        )
    elif sort_by == "upcoming":
        entries.sort(
            key=lambda entry: attrgetter("years", "months", "days")(
                entry.next_occurrence_in(today)
            ),
            reverse=sort_order == "desc",
        )
    elif sort_by == "recent":
        entries.sort(
            key=lambda entry: attrgetter("years", "months", "days")(
                entry.prev_occurrence_in(today)
            ),
            reverse=sort_order == "desc",
        )
    elif sort_by == "age":
        entries.sort(
            key=lambda entry: (
                age
                if (age := entry.get_age()) is not None
                else float("inf" if sort_order == "asc" else "-inf")
            ),
            reverse=sort_order == "desc",
        )

    if view_style == "simple":
        print("Birthdays 🎂")
        for entry in entries:
            emoji = date_to_emoji(entry.year, entry.month, entry.day)
            age = entry.get_age()
            next_in = entry.next_occurrence_in(today)
            prev_in = entry.prev_occurrence_in(today)

            print(f"{emoji:<2} {entry}")
            if entry.is_today():
                age = f"{to_ordinal(age)} " if age is not None else ""
                print(f"Has a {age}birthday today 🥳")
            else:
                age = f"{age} y.o., " if age is not None else ""
                months = tuple(
                    f" {delta.months} month{'s' if delta.months > 1 else ''}"
                    if delta.months > 0
                    else ""
                    for delta in (next_in, prev_in)
                )
                days = tuple(
                    f"{' and' if delta.months else ''} {delta.days} day{'s' if delta.days > 1 else ''}"
                    if delta.days > 0
                    else ""
                    for delta in (next_in, prev_in)
                )
                if sort_by != "recent":
                    print(f"{age}Next in{months[0]}{days[0]}")
                elif sort_by == "recent":
                    print(f"{age}Previous in{months[1]}{days[1]}")


# ==========================================
#               ARGPARSE CLI
# ==========================================


def setup_parser() -> argparse.ArgumentParser:
    """Build the CLI interface."""

    parser = argparse.ArgumentParser(
        prog="birthdays",
        description="A robust CLI tool to manage, merge, and track birthdays.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    parser_list = subparsers.add_parser("list", help="Display saved birthdays")
    parser_list.add_argument(
        "--sort",
        choices=["name", "date", "upcoming", "recent", "age"],
        default="upcoming",
        help="How to sort the output",
    )
    parser_list.add_argument(
        "--order",
        choices=["asc", "desc"],
        default="asc",
        help="In which order to sort the output",
    )
    parser_list.add_argument(
        "--view",
        choices=["simple", "table", "calendar"],
        default="simple",
        help="Visual presentation style",
    )
    parser_list.add_argument(
        "-f",
        "--file",
        type=Path,
        help="Read directly from a .vcf or .json file without modifying the database",
    )

    parser_add = subparsers.add_parser("add", help="Manually add a new birthday")
    parser_add.add_argument("name", type=str, help="Full name of the person")
    parser_add.add_argument("date", type=str, help="Birthday (YYYY-MM-DD | MM-DD)")
    parser_add.add_argument("--note", type=str, help="Optional note to attach")
    parser_add.add_argument(
        "--leap-system",
        choices=["before", "after"],
        default="before",
        help="When leaplings celebrate in non-leap years (default: before)",
    )

    parser_edit = subparsers.add_parser("edit", help="Modify an existing entry")
    parser_edit.add_argument("identifier", type=str, help="Name or UUID of the person")
    parser_edit.add_argument("--name", type=str, help="Update the full name")
    parser_edit.add_argument(
        "--date", type=str, help="Update the birthday (YYYY-MM-DD | MM-DD)"
    )
    parser_edit.add_argument("--note", type=str, help="Update the attached note")
    parser_edit.add_argument(
        "--leap-system",
        choices=["before", "after"],
        help="Update when this leapling celebrates in non-leap years",
    )

    parser_delete = subparsers.add_parser("delete", help="Delete an entry")
    parser_delete.add_argument(
        "identifier", type=str, help="Name or UUID of the person"
    )
    parser_delete.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )

    parser_import = subparsers.add_parser(
        "import", help="Import birthdays from a vCard file"
    )
    parser_import.add_argument("file", type=Path, help="Path to the .vcf file")
    parser_import.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip interactive collision prompts and auto-merge safe entries",
    )
    parser_import.add_argument(
        "--leap-system",
        choices=["before", "after"],
        default="before",
        help="Default leap system to assign to imported contacts",
    )

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()

    if args.command == "list":
        ...  # load_db(), sort, display_birthdays()
    elif args.command == "add":
        ...  # create entry, load_db(), append, save_db()
    elif args.command == "edit":
        ...
    elif args.command == "delete":
        ...  # load_db(), remove entry, save_db()
    elif args.command == "import":
        ...  # parse_vcards(), load_db(), merge_entries(), save_db()


if __name__ == "__main__":
    main()
