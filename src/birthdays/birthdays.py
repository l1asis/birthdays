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
from dataclasses import asdict, dataclass, field
from operator import attrgetter
from pathlib import Path
from typing import Any, List, Literal, Optional, overload

from dateutil.relativedelta import relativedelta
from platformdirs import user_cache_path, user_data_path

from . import __about__, __version__
from .emojis import date_to_emoji, should_use_emoji

VCARD = re.compile(r"BEGIN:VCARD.*?END:VCARD", flags=re.DOTALL | re.IGNORECASE)
FULL_NAME = re.compile(r"^FN(;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)
BIRTHDAY = re.compile(r"^BDAY(?:;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)
DATE = re.compile(r"^(\d{4}|--)?-?(0[1-9]|1[0-2])-?(0[1-9]|[12]\d|3[01])$")
NOTE = re.compile(r"^NOTE(;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)
CATEGORIES = re.compile(
    r"^CATEGORIES(?:;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE
)
UNFOLD = re.compile(r"\r?\n[ \t]")  # glues lines that start with a space or tab
UNFOLD_SOFT = re.compile(r"=\r?\n")  # glues lines that end with an '='

MOTD_MARKER_START = "# >>> birthdays motd >>>"
MOTD_MARKER_END = "# <<< birthdays motd <<<"
MOTD_BLOCK_REGEX = re.compile(
    rf"{re.escape(MOTD_MARKER_START)}.*?{re.escape(MOTD_MARKER_END)}\n?",
    flags=re.DOTALL,
)

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
    groups: list[str] = field(default_factory=list[str])
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
            from_date.month == this_year.month and from_date.day <= this_year.day
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
        return relativedelta(from_date, self.get_prev_occurrence(from_date))

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
        dir_path = Path(custom_path)
    else:
        dir_path = user_data_path(
            "birthdays",
            "l1asis",
            ensure_exists=True,
        )

    dir_path.mkdir(parents=True, exist_ok=True)

    return dir_path / "birthdays.json"


def as_birthday_entry(dictionary: dict[str, Any]) -> BirthdayEntry:
    """Read a JSON dictionary and safely convert it into BirthdayEntry."""
    return BirthdayEntry(
        dictionary["id"],
        dictionary["full_name"],
        dictionary["month"],
        dictionary["day"],
        dictionary.get("year"),
        dictionary.get("notes"),
        dictionary.get("groups", []),
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


def should_run_today() -> bool:
    """Check if the MOTD has already been displayed today."""
    cache_dir = user_cache_path("birthdays", "l1asis", ensure_exists=True)
    cache_file = cache_dir / "motd_last_run.txt"

    today_str = datetime.date.today().isoformat()

    if cache_file.exists():
        last_run = cache_file.read_text(encoding="utf-8").strip()
        if last_run == today_str:
            return False

    cache_file.write_text(today_str, encoding="utf-8")
    return True


# ==========================================
#          SHELL INTEGRATION APIs
# ==========================================


def get_target_shell_configs() -> List[Path]:
    """Detect OS and current user shell to return candidate RC file paths."""
    home = Path.home()
    candidates: List[Path] = []

    if sys.platform == "win32":
        # Windows PowerShell Profile locations
        ps_dirs = [
            home / "Documents" / "PowerShell",
            home / "Documents" / "WindowsPowerShell",
        ]
        for ps_dir in ps_dirs:
            candidates.append(ps_dir / "Microsoft.PowerShell_profile.ps1")
    else:
        # Linux / macOS Shell Detection
        user_shell = os.getenv("SHELL", "")

        if "zsh" in user_shell:
            candidates.append(home / ".zshrc")
        elif "fish" in user_shell:
            candidates.append(home / ".config" / "fish" / "config.fish")
        elif "bash" in user_shell:
            if sys.platform == "darwin":
                candidates.append(home / ".bash_profile")
            candidates.append(home / ".bashrc")
        else:
            # Fallback scan for common POSIX config files if $SHELL is ambiguous
            for rc in [".zshrc", ".bashrc", ".bash_profile"]:
                if (home / rc).exists():
                    candidates.append(home / rc)

    return candidates


def build_motd_command(args: argparse.Namespace) -> str:
    """Reconstruct the exact command string from parsed flags."""
    cmd_parts = ["birthdays", "motd"]
    if args.days != 7:
        cmd_parts.append(f"--days {args.days}")
    if args.limit != 3:
        cmd_parts.append(f"--limit {args.limit}")
    for group in flatten_groups(getattr(args, "group", None)):
        cmd_parts.append(f"--group {group}")
    if getattr(args, "match", "any") != "any":
        cmd_parts.append(f"--match {args.match}")
    if getattr(args, "quiet_if_empty", False):
        cmd_parts.append("--quiet-if-empty")
    if getattr(args, "show_date", False):
        cmd_parts.append("--show-date")
    if getattr(args, "no_emoji", False):
        cmd_parts.append("--no-emoji")
    if getattr(args, "once_per_day", False):
        cmd_parts.append("--once-per-day")

    return " ".join(cmd_parts)


def enable_motd_hook(args: argparse.Namespace) -> None:
    """Inject or update the MOTD startup block in the shell configuration."""
    if getattr(args, "rc_file", None):
        configs = [args.rc_file]
    else:
        configs = get_target_shell_configs()

    if not configs:
        print("Error: Could not determine shell config file to hook into.")
        sys.exit(1)

    motd_cmd = build_motd_command(args)
    block_content = f"{MOTD_MARKER_START}\n{motd_cmd}\n{MOTD_MARKER_END}\n"

    for config_path in configs:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        existing_text = (
            config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        )

        match = MOTD_BLOCK_REGEX.search(existing_text)
        if match:
            current_block = match.group(0)
            if current_block.strip() == block_content.strip():
                print(f"MOTD is already enabled and up to date in '{config_path}'.")
                continue
            else:
                new_text = MOTD_BLOCK_REGEX.sub(block_content, existing_text)
                config_path.write_text(new_text, encoding="utf-8")
                print(f"Updated MOTD hook parameters in '{config_path}'.")
                continue

        separator = "" if not existing_text or existing_text.endswith("\n") else "\n"
        new_text = f"{existing_text}{separator}\n{block_content}"
        config_path.write_text(new_text, encoding="utf-8")
        print(f"Successfully enabled MOTD hook in '{config_path}'.")


def disable_motd_hook() -> None:
    """Remove the MOTD startup block from shell configuration files."""
    configs = get_target_shell_configs()
    removed_any = False

    for config_path in configs:
        if not config_path.exists():
            continue

        existing_text = config_path.read_text(encoding="utf-8")
        if MOTD_BLOCK_REGEX.search(existing_text):
            new_text = MOTD_BLOCK_REGEX.sub("", existing_text).rstrip() + "\n"
            config_path.write_text(new_text, encoding="utf-8")
            print(f"Disabled MOTD hook in '{config_path}'.")
            removed_any = True

    if not removed_any:
        print("MOTD hook is not currently enabled in any detected shell config.")


# ==========================================
#            CORE LOGIC APIs
# ==========================================


def decode_vcard_text(raw_text: str, parameters: str | None) -> str:
    """Safely decode Quoted-Printable or Base64 vCard strings."""
    if not parameters:
        return raw_text.strip()

    parameters = parameters.upper()
    if "ENCODING=QUOTED-PRINTABLE" in parameters:
        unquoted = quopri.decodestring(raw_text)
        if "CHARSET=UTF-8" in parameters:
            return unquoted.decode("utf-8", errors="replace").strip()
        return unquoted.decode("latin1", errors="replace").strip()

    elif "ENCODING=B" in parameters:
        unbased = base64.standard_b64decode(raw_text)
        if "CHARSET=UTF-8" in parameters:
            return unbased.decode("utf-8", errors="replace").strip()
        return unbased.decode("latin1", errors="replace").strip()

    return raw_text.strip()


def normalize_group(group: str) -> str:
    """Normalize a single group label for storage and matching."""
    return group.strip().replace(r"\n", " ").replace(r"\,", ",").casefold()


def flatten_groups(raw_groups: Collection[str] | None) -> list[str]:
    """Normalize an input collection of groups, splitting comma-separated values."""
    flattened: list[str] = []
    seen: set[str] = set()

    for raw_group in raw_groups or []:
        for group in raw_group.split(","):
            normalized = normalize_group(group)
            if normalized and normalized not in seen:
                seen.add(normalized)
                flattened.append(normalized)

    return flattened


def merge_group_lists(
    existing_groups: list[str], incoming_groups: list[str]
) -> list[str]:
    """Merge two normalized group lists while preserving order."""
    merged: list[str] = []
    seen: set[str] = set()

    for group in (*existing_groups, *incoming_groups):
        if group and group not in seen:
            seen.add(group)
            merged.append(group)

    return merged


def matches_group_filter(
    entry: BirthdayEntry, group_filters: list[str], match_mode: Literal["any", "all"]
) -> bool:
    """Check whether an entry should survive the active group filter."""
    if not group_filters:
        return True

    entry_groups = set(entry.groups)
    filter_groups = set(group_filters)

    if match_mode == "all":
        return filter_groups.issubset(entry_groups)

    return bool(entry_groups & filter_groups)


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
    """Extract names, birthdays, and notes from all vCard formats."""
    with open(vcf_file, "r", encoding="utf-8") as file:
        raw_text = file.read()

    unfolded_text = UNFOLD.sub("", raw_text)
    unfolded_text = UNFOLD_SOFT.sub("", unfolded_text)

    vcards: list[str] = VCARD.findall(unfolded_text)
    birthdays: List[BirthdayEntry] = []

    for vcard in vcards:
        fn_match = FULL_NAME.search(vcard)
        bday_match = BIRTHDAY.search(vcard)
        note_match = NOTE.search(vcard)
        categories_match = CATEGORIES.search(vcard)

        if fn_match is not None:
            full_name = decode_vcard_text(fn_match.group(2), fn_match.group(1))

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
                    notes = None
                    if note_match is not None:
                        raw_note = decode_vcard_text(
                            note_match.group(2), note_match.group(1)
                        )
                        notes = raw_note.replace(r"\n", " ").replace(r"\,", ",")

                    groups: list[str] = []
                    if categories_match is not None:
                        raw_categories = decode_vcard_text(
                            categories_match.group(2), categories_match.group(1)
                        )
                        groups = flatten_groups(
                            [
                                category.replace(r"\n", " ")
                                for category in re.split(r"(?<!\\),", raw_categories)
                            ]
                        )

                    birthdays.append(
                        BirthdayEntry(
                            uuid.uuid4().hex,
                            full_name,
                            month,
                            day,
                            year,
                            notes,
                            groups,
                            leap_system,
                        )
                    )

    return birthdays


def merge_pair(
    existing: BirthdayEntry, incoming: BirthdayEntry, interactive: bool = True
) -> BirthdayEntry:
    """Combine data of two entries meaningfully."""

    existing_note = (
        existing.notes.strip() if existing.notes and existing.notes.strip() else None
    )
    incoming_note = (
        incoming.notes.strip() if incoming.notes and incoming.notes.strip() else None
    )

    merged_notes = tuple(n for n in (existing_note, incoming_note) if n)
    merged_notes = "; ".join(merged_notes) if merged_notes else None

    existing_groups = flatten_groups(existing.groups)
    incoming_groups = flatten_groups(incoming.groups)

    if interactive:
        if existing_note != incoming_note:
            final_notes = None
            if not existing_note:
                if confirm(
                    f"Incoming contact has a note: {incoming_note!r}. Keep it?",
                    required=True,
                ):
                    final_notes = incoming_note
            elif not incoming_note:
                if not confirm(
                    "Incoming contact has no notes. "
                    f"Delete existing note ({existing_note!r})?",
                    required=True,
                ):
                    final_notes = existing_note
            else:
                options = (
                    f"Keep existing: {existing_note!r}",
                    f"Keep incoming: {incoming_note!r}",
                    f"Merge both:    {merged_notes}",
                )

                notes_choice = choose(
                    options,
                    prompt="\nNotes differ. How would you like to resolve this?",
                    required=True,
                )

                if notes_choice == "1":
                    final_notes = existing_note
                elif notes_choice == "2":
                    final_notes = incoming_note
                else:
                    final_notes = merged_notes
        else:
            final_notes = existing_note

        if existing_groups != incoming_groups:
            final_groups = None
            if not existing_groups:
                if confirm(
                    f"Incoming contact has groups: {', '.join(incoming_groups)!r}. "
                    "Keep them?",
                    required=True,
                ):
                    final_groups = incoming_groups
                else:
                    final_groups = existing_groups
            elif not incoming_groups:
                if not confirm(
                    "Incoming contact has no groups. "
                    f"Delete existing groups ({', '.join(existing_groups)!r})?",
                    required=True,
                ):
                    final_groups = existing_groups
                else:
                    final_groups = []
            else:
                merged_groups = merge_group_lists(existing_groups, incoming_groups)
                options = (
                    f"Keep existing: {', '.join(existing_groups)}",
                    f"Keep incoming: {', '.join(incoming_groups)}",
                    f"Merge both:    {', '.join(merged_groups)}",
                )

                groups_choice = choose(
                    options,
                    prompt="\nGroups differ. How would you like to resolve this?",
                    required=True,
                )

                if groups_choice == "1":
                    final_groups = existing_groups
                elif groups_choice == "2":
                    final_groups = incoming_groups
                else:
                    final_groups = merged_groups
        else:
            final_groups = existing_groups

        return BirthdayEntry(
            existing.id,
            incoming.full_name
            if existing.full_name != incoming.full_name
            and confirm("Change the full name?")
            else existing.full_name,
            incoming.month
            if existing.month != incoming.month and confirm("Change the month?")
            else existing.month,
            incoming.day
            if existing.day != incoming.day and confirm("Change the day?")
            else existing.day,
            incoming.year
            if existing.year is None
            or (existing.year != incoming.year and confirm("Change the year?"))
            else existing.year,
            final_notes,
            final_groups,
            incoming.leap_system
            if existing.leap_system != incoming.leap_system
            and confirm("Change the leap system?")
            else existing.leap_system,
        )
    return BirthdayEntry(
        existing.id,
        incoming.full_name,
        incoming.month,
        incoming.day,
        incoming.year if existing.year is None else existing.year,
        merged_notes,
        merge_group_lists(existing_groups, incoming_groups),
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
                    prompt=(
                        f"\nMultiple exact matches for '{new_entry.full_name}'. "
                        "Which one to merge into?"
                    ),
                    extra={"S": "Skip this contact entirely"},
                    required=True,
                )

                if choice == "S":
                    continue

                match = existing_map[new_entry.full_name][int(choice) - 1]
            else:
                match = existing_map[new_entry.full_name][0]

            match_note = (match.notes.strip() or None) if match.notes else None
            new_note = (new_entry.notes.strip() or None) if new_entry.notes else None

            if (
                match.month == new_entry.month
                and match.day == new_entry.day
                and match.year == new_entry.year
                and match.leap_system == new_entry.leap_system
                and match_note == new_note
            ):
                continue

            if interactive:
                print(
                    (
                        f"\nExact name match found for '{new_entry.full_name}', "
                        "but data differs."
                    )
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


def find_entry(db: List[BirthdayEntry], identifier: str) -> BirthdayEntry | None:
    """Locate an entry by UUID, name, date, or fuzzy match."""

    for entry in db:
        if entry.id == identifier:
            return entry

    matches: list[BirthdayEntry] = []
    ident_lower = identifier.casefold()

    date_match = DATE.match(identifier)
    year = month = day = None
    if date_match:
        year_group = date_match.group(1)
        year = int(year_group) if year_group and year_group != "--" else None
        month = int(date_match.group(2))
        day = int(date_match.group(3))

    for entry in db:
        if entry.full_name.casefold() == ident_lower:
            matches.append(entry)
        elif (
            date_match
            and entry.month == month
            and entry.day == day
            and (not year or entry.year == year)
        ):
            matches.append(entry)
        elif ident_lower in entry.full_name.casefold():
            matches.append(entry)
        elif entry.notes and ident_lower in entry.notes.casefold():
            matches.append(entry)
        elif ident_lower in {group.casefold() for group in entry.groups}:
            matches.append(entry)

    if not matches:
        db_names = [e.full_name for e in db]
        close_names = difflib.get_close_matches(identifier, db_names, n=5, cutoff=0.6)

        if close_names:
            close_names_set = set(close_names)
            for entry in db:
                if entry.full_name in close_names_set:
                    matches.append(entry)

    if not matches:
        print(f"Error: No entry found matching '{identifier}'.")
        return None

    if len(matches) == 1:
        return matches[0]

    choice = choose(
        matches,
        prompt=f"\nMultiple entries found for '{identifier}'. Which one did you mean?",
        extra={"S": "Skip/Cancel"},
        required=True,
    )
    if choice == "S":
        return None

    return matches[int(choice) - 1]


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


def sort_entries(
    entries: List[BirthdayEntry],
    sort_by: Literal["name", "date", "upcoming", "recent", "age"] = "upcoming",
    sort_order: Literal["asc", "desc"] = "desc",
) -> List[BirthdayEntry]:
    """Sort birthday entries by criteria and order."""
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

    return entries


def display_birthdays(
    entries: List[BirthdayEntry],
    sort_by: Literal["name", "date", "upcoming", "recent", "age"] = "upcoming",
    sort_order: Literal["asc", "desc"] = "desc",
    view_style: Literal["simple", "table", "calendar", "groups"] = "simple",
    use_emoji: bool = True,
    should_sort: bool = True,
    show_header_date: bool = False,
) -> None:
    """Handle all terminal printing."""
    today = datetime.date.today()

    if should_sort:
        entries = sort_entries(entries, sort_by, sort_order)

    if view_style == "groups":
        if show_header_date:
            date_str = today.strftime("%A, %b %d")
            print(f"Birthdays for {date_str}{' 🎂' if use_emoji else ''}")
        else:
            print(f"Birthdays{' 🎂' if use_emoji else ''}")

        grouped_entries: dict[str, list[BirthdayEntry]] = defaultdict(list)
        for entry in entries:
            primary_group = entry.groups[0] if entry.groups else "ungrouped"
            grouped_entries[primary_group].append(entry)

        ordered_groups = sorted(
            grouped_entries,
            key=lambda group: (group == "ungrouped", group.casefold()),
        )

        for group_name in ordered_groups:
            print(f"\n{group_name}")
            for entry in grouped_entries[group_name]:
                age = entry.get_age()
                next_in = entry.next_occurrence_in(today)
                prev_in = entry.prev_occurrence_in(today)

                emoji = date_to_emoji(entry.year, entry.month, entry.day)
                group_suffix = (
                    f" (also in: {', '.join(entry.groups[1:])})"
                    if len(entry.groups) > 1
                    else ""
                )
                print(f"{emoji if use_emoji else '->'}  {entry}{group_suffix}")

                if entry.is_today():
                    age = f"{to_ordinal(age)} " if age is not None else ""
                    print(f"    Has a {age}birthday today{' 🥳' if use_emoji else '!'}")
                else:
                    age = f"{age} y.o., " if age is not None else ""
                    months = tuple(
                        f" {delta.months} month{'s' if delta.months > 1 else ''}"
                        if delta.months > 0
                        else ""
                        for delta in (next_in, prev_in)
                    )
                    days = tuple(
                        (
                            f"{' and' if delta.months else ''} "
                            f"{delta.days} day{'s' if delta.days > 1 else ''}"
                        )
                        if delta.days > 0
                        else ""
                        for delta in (next_in, prev_in)
                    )
                    if sort_by != "recent":
                        print(f"    {age}Next in{months[0]}{days[0]}")
                    elif sort_by == "recent":
                        print(f"    {age}Previous:{months[1]}{days[1]} ago")

    elif view_style == "simple":
        if show_header_date:
            date_str = today.strftime("%A, %b %d")
            print(f"Birthdays for {date_str}{' 🎂' if use_emoji else ''}")
        else:
            print(f"Birthdays{' 🎂' if use_emoji else ''}")

        for entry in entries:
            age = entry.get_age()
            next_in = entry.next_occurrence_in(today)
            prev_in = entry.prev_occurrence_in(today)

            emoji = date_to_emoji(entry.year, entry.month, entry.day)
            print(f"{emoji if use_emoji else '->'}  {entry}")

            if entry.is_today():
                age = f"{to_ordinal(age)} " if age is not None else ""
                print(f"    Has a {age}birthday today{' 🥳' if use_emoji else '!'}")
            else:
                age = f"{age} y.o., " if age is not None else ""
                months = tuple(
                    f" {delta.months} month{'s' if delta.months > 1 else ''}"
                    if delta.months > 0
                    else ""
                    for delta in (next_in, prev_in)
                )
                days = tuple(
                    (
                        f"{' and' if delta.months else ''} "
                        f"{delta.days} day{'s' if delta.days > 1 else ''}"
                    )
                    if delta.days > 0
                    else ""
                    for delta in (next_in, prev_in)
                )
                if sort_by != "recent":
                    print(f"    {age}Next in{months[0]}{days[0]}")
                elif sort_by == "recent":
                    print(f"    {age}Previous:{months[1]}{days[1]} ago")


def display_motd(
    entries: List[BirthdayEntry],
    horizon_days: int = 7,
    limit: int = 3,
    quiet_if_empty: bool = False,
    use_emoji: bool = True,
    show_header_date: bool = False,
) -> None:
    """Print a minimal summary of upcoming birthdays."""
    today = datetime.date.today()

    upcoming = [
        entry
        for entry in entries
        if (entry.get_next_occurrence(today) - today).days <= horizon_days
    ]

    if not upcoming and not quiet_if_empty:
        print(
            f"No upcoming birthdays for the next {horizon_days} "
            f"day{'s' if horizon_days != 1 else ''}!"
        )
        print("Run 'birthdays list' to see all.")
        return
    elif not upcoming and quiet_if_empty:
        return

    upcoming = sort_entries(upcoming, sort_by="upcoming", sort_order="asc")
    printable = upcoming[:limit]
    truncated = upcoming[limit:]

    more_today_count = sum(1 for e in truncated if e.is_today())
    more_upcoming_count = len(truncated) - more_today_count

    display_birthdays(
        printable,
        view_style="simple",
        use_emoji=use_emoji,
        should_sort=False,
        show_header_date=show_header_date,
    )

    if more_today_count > 0:
        print(f"...and {more_today_count} more today!")

    if more_upcoming_count > 0:
        timeframe = (
            "this week" if horizon_days == 7 else f"in the next {horizon_days} days"
        )
        print(f"...and {more_upcoming_count} more upcoming {timeframe}.")
        print("Run 'birthdays list' to see all.")


# ==========================================
#               ARGPARSE CLI
# ==========================================


def setup_parser() -> argparse.ArgumentParser:
    """Build the CLI interface."""

    parser = argparse.ArgumentParser(
        prog="birthdays",
        description="A robust CLI tool to manage, merge, and track birthdays.",
    )

    parser.add_argument(
        "--version",
        action="version",
        help="Show program's version number and exit",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--about",
        action="store_true",
        help="Show information about this program",
    )
    parser.add_argument(
        "--no-emoji",
        action="store_true",
        help="Disable the use of emojis globally",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

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
        default="desc",
        help="In which order to sort the output",
    )
    parser_list.add_argument(
        "--view",
        choices=["simple", "table", "calendar", "groups"],
        default="simple",
        help="Visual presentation style",
    )
    parser_list.add_argument(
        "-g",
        "--group",
        action="append",
        help="Filter entries by one or more groups",
    )
    parser_list.add_argument(
        "--match",
        choices=["any", "all"],
        default="any",
        help="Match any selected group or require all of them",
    )
    parser_list.add_argument(
        "-f",
        "--file",
        type=Path,
        help="Read directly from a .vcf or .json file without modifying the database",
    )
    parser_list.add_argument(
        "--leap-system",
        choices=["before", "after"],
        default="before",
        help="Fallback leap system when reading dynamically from a .vcf file",
    )

    parser_add = subparsers.add_parser("add", help="Manually add a new birthday")
    parser_add.add_argument("name", type=str, help="Full name of the person")
    parser_add.add_argument("date", type=str, help="Birthday (YYYY-MM-DD | MM-DD)")
    parser_add.add_argument("--note", type=str, help="Optional note to attach")
    parser_add.add_argument(
        "-g",
        "--group",
        action="append",
        help="Assign one or more groups to the new entry",
    )
    parser_add.add_argument(
        "--leap-system",
        dest="leap_system",
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
        "-g",
        "--group",
        action="append",
        help="Assign one or more groups to the entry",
    )
    parser_edit.add_argument(
        "--leap-system",
        dest="leap_system",
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
        "import",
        help="Import birthdays from a vCard or JSON file",
    )
    parser_import.add_argument("file", type=Path, help="Path to the .vcf file")
    parser_import.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip interactive collision prompts and auto-merge safe entries",
    )
    parser_import.add_argument(
        "-g",
        "--group",
        action="append",
        help="Assign imported contacts to one or more groups",
    )
    parser_import.add_argument(
        "--leap-system",
        dest="leap_system",
        choices=["before", "after"],
        default="before",
        help="Default leap system to assign to imported contacts",
    )

    parser_motd = subparsers.add_parser(
        "motd", help="Display the MOTD or manage the shell startup hook"
    )
    parser_motd.add_argument(
        "action",
        nargs="?",
        choices=["enable", "disable"],
        help="Optional action: 'enable' or 'disable' shell startup hook.",
    )
    parser_motd.add_argument(
        "--rc-file",
        type=Path,
        help="Path to a custom shell config file (overrides automatic detection)",
    )
    parser_motd.add_argument(
        "-g",
        "--group",
        action="append",
        help="Filter entries by one or more groups",
    )
    parser_motd.add_argument(
        "--match",
        choices=["any", "all"],
        default="any",
        help="Match any selected group or require all of them",
    )
    parser_motd.add_argument(
        "--days", type=int, default=7, help="Days ahead to check for birthdays"
    )
    parser_motd.add_argument(
        "--limit", type=int, default=3, help="Max entries to print directly"
    )
    parser_motd.add_argument(
        "--quiet-if-empty", action="store_true", help="Exit silently if no birthdays"
    )
    parser_motd.add_argument(
        "--show-date", action="store_true", help="Include today's date in title"
    )
    parser_motd.add_argument(
        "--once-per-day",
        action="store_true",
        help="Only display the MOTD once per calendar day",
    )

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()

    use_emoji = should_use_emoji(args.no_emoji)

    if args.about:
        print(__about__ if use_emoji else __about__.replace("🔥", " &"))
        sys.exit(0)

    if not args.command:
        parser.error("the following arguments are required: command")

    db_path = get_database_path()

    if args.command == "list":
        if args.file:
            if not args.file.exists():
                print(f"Error: File '{args.file}' not found.")
                sys.exit(1)
            if args.file.suffix.lower() in [".vcf", ".vcard"]:
                entries = parse_vcards(args.file, args.leap_system)
            else:
                entries = load_database(args.file)
        else:
            entries = load_database(db_path)

        if not entries:
            print("No birthdays found.")
            return

        display_birthdays(
            entries,
            sort_by=args.sort,
            sort_order=args.order,
            view_style=args.view,
            use_emoji=use_emoji,
        )

    elif args.command == "add":
        db = load_database(db_path)

        date_match = DATE.match(args.date)
        if not date_match:
            print("Error: Invalid date format. Use YYYY-MM-DD or MM-DD.")
            sys.exit(1)

        year_group = date_match.group(1)
        year = int(year_group) if year_group and year_group != "--" else None
        month = int(date_match.group(2))
        day = int(date_match.group(3))

        try:
            new_entry = BirthdayEntry(
                id=uuid.uuid4().hex,
                full_name=args.name,
                month=month,
                day=day,
                year=year,
                notes=args.note,
                leap_system=args.leap_system,
            )
        except ValueError as e:
            print(f"Error creating entry: {e}")
            sys.exit(1)

        db.append(new_entry)
        save_database(db, db_path)
        print(f"Added: {new_entry}")

    elif args.command == "edit":
        db = load_database(db_path)
        target = find_entry(db, args.identifier)
        if not target:
            sys.exit(1)

        if args.name:
            target.full_name = args.name

        if args.date:
            date_match = DATE.match(args.date)
            if not date_match:
                print("Error: Invalid date format. Use YYYY-MM-DD or MM-DD.")
                sys.exit(1)

            year_group = date_match.group(1)
            target.year = int(year_group) if year_group and year_group != "--" else None
            target.month = int(date_match.group(2))
            target.day = int(date_match.group(3))

        if args.note is not None:
            target.notes = args.note if args.note.strip() else None

        if args.leap_system:
            target.leap_system = args.leap_system

        save_database(db, db_path)
        print(f"Updated: {target}")

    elif args.command == "delete":
        db = load_database(db_path)
        target = find_entry(db, args.identifier)
        if not target:
            sys.exit(1)

        if not args.yes:
            if not confirm(f"Are you sure you want to delete {target}?"):
                print("Deletion cancelled.")
                return

        db = [e for e in db if e.id != target.id]
        save_database(db, db_path)
        print(f"Deleted '{target.full_name}'.")

    elif args.command == "import":
        if not args.file.exists():
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)

        db = load_database(db_path)

        if args.file.suffix.lower() in [".vcf", ".vcard"]:
            incoming = parse_vcards(args.file, args.leap_system)
        else:
            incoming = load_database(args.file)

        print(f"Loaded {len(incoming)} contacts from {args.file.name}.")

        merged_db = merge_entries(db, incoming, interactive=not args.yes)
        save_database(merged_db, db_path)

        added_count = len(merged_db) - len(db)

        id_to_entry_map = {e.id: e for e in db}

        updated_count = sum(
            1
            for e in merged_db
            if e.id in id_to_entry_map and e != id_to_entry_map[e.id]
        )

        print("\nImport complete.")
        if not added_count and not updated_count:
            print("The database was left unchanged.")
        else:
            if added_count:
                print(f"Added {added_count} entr{'y' if added_count == 1 else 'ies'}.")
            if updated_count:
                print(
                    f"Updated {updated_count} "
                    f"entr{'y' if updated_count == 1 else 'ies'}."
                )

    elif args.command == "motd":
        if args.action == "enable":
            enable_motd_hook(args)
        elif args.action == "disable":
            disable_motd_hook()
        else:
            if args.once_per_day and not should_run_today():
                sys.exit(0)

            entries = load_database(db_path)
            display_motd(
                entries,
                horizon_days=args.days,
                limit=args.limit,
                quiet_if_empty=args.quiet_if_empty,
                use_emoji=use_emoji,
                show_header_date=args.show_date,
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
