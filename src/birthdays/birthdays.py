import argparse
import base64
import calendar
import datetime
import json
import os
import quopri
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, List, Literal, Optional

from dateutil.relativedelta import relativedelta
from platformdirs import user_data_path

VCARD = re.compile(r"BEGIN:VCARD.*?END:VCARD", flags=re.DOTALL | re.IGNORECASE)
FULL_NAME = re.compile(r"^FN(;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)
BIRTHDAY = re.compile(r"^BDAY(?:;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)
DATE = re.compile(r"^(\d{4}|--)?-?(0[1-9]|1[0-2])-?(0[1-9]|[12]\d|3[01])$")

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
                            int(date_match.group(1)),
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


def merge_entries(
    existing: List[BirthdayEntry],
    incoming: List[BirthdayEntry],
    interactive: bool = True,
) -> List[BirthdayEntry]:
    """Merge two lists using fuzzy string matching to detect similar names."""
    ...


# ==========================================
#             PRESENTATION APIs
# ==========================================


def display_birthdays(
    entries: List[BirthdayEntry],
    sort_by: Literal["name", "date", "upcoming", "recent", "age"] = "upcoming",
    view_style: Literal["simple", "table", "calendar"] = "simple",
) -> None:
    """Handle all terminal printing."""
    ...


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
