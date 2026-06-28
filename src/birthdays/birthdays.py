from dataclasses import dataclass
from pathlib import Path
import datetime
import re
import argparse
from typing import Optional, List, Literal
from dateutil.relativedelta import relativedelta
import quopri
import base64
import uuid
import calendar


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

    def get_next_occurrence(self, from_date: datetime.date) -> datetime.date:
        """Calculate the exact date of the next birthday."""
        ...

    def get_prev_occurrence(self, from_date: datetime.date) -> datetime.date:
        """Calculate the exact date of the previous birthday."""
        ...

    def next_occurrence_in(self, from_date: datetime.date) -> relativedelta:
        """Calculate the exact distance to the next birthday."""
        ...

    def prev_occurrence_in(self, from_date: datetime.date) -> relativedelta | None:
        """Calculate the exact distance to the previous birthday."""
        ...


# ==========================================
#               STORAGE APIs
# ==========================================


def get_database_path() -> Path:
    """Resolve OS-specific config path (e.g., ~/.config/birthdays/db.json)."""
    ...


def load_database(db_path: Path) -> List[BirthdayEntry]:
    """Read the JSON file and inflate it into BirthdayEntry objects."""
    ...


def save_database(entries: List[BirthdayEntry], db_path: Path) -> None:
    """Serialize BirthdayEntry objects and write them to the JSON file."""
    ...


# ==========================================
#            CORE LOGIC APIs
# ==========================================


def day_might_exist(year: int | None, month: int, day: int) -> bool:
    """Check if a day is valid for a given month, handling missing years safely."""
    _, num_days = calendar.monthrange(year if year is not None else 2024, month)
    return 1 <= day <= num_days


def parse_vcards(vcf_file: Path) -> List[BirthdayEntry]:
    """Extract names and birthdays from all vCard formats."""

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

    parser_edit = subparsers.add_parser("edit", help="Modify an existing entry")
    parser_edit.add_argument("identifier", type=str, help="Name or UUID of the person")
    parser_edit.add_argument("--name", type=str, help="Update the full name")
    parser_edit.add_argument(
        "--date", type=str, help="Update the birthday (YYYY-MM-DD | MM-DD)"
    )
    parser_edit.add_argument("--note", type=str, help="Update the attached note")

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
