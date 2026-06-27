import hashlib
import pathlib
import datetime
import typing
import re
from dateutil.relativedelta import relativedelta
import quopri
import base64
from emojis import ALL_EMOJIS

VCARD = re.compile(r"BEGIN:VCARD.*?END:VCARD", flags=re.DOTALL | re.IGNORECASE)
FULL_NAME = re.compile(r"^FN(;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)
BIRTHDAY = re.compile(r"^BDAY(?:;[^:]*)?:(.*)$", flags=re.MULTILINE | re.IGNORECASE)


def birthday_to_emoji(year: int | None, month: int, day: int) -> str:
    if isinstance(year, int):
        encoded = f"{year}-{month}-{day}".encode("utf-8")
    else:
        encoded = f"{month}-{day}".encode("utf-8")

    hashed = hashlib.sha256(encoded).hexdigest()

    return ALL_EMOJIS[int(hashed, 16) % len(ALL_EMOJIS)]


def resolve_vcard_full_name(match: re.Match[str]) -> str:
    parameters = match.group(1)
    full_name = match.group(2)

    if not parameters:
        return full_name

    if "ENCODING=QUOTED-PRINTABLE" in parameters:
        unquoted = quopri.decodestring(full_name)
        if "CHARSET=UTF-8" in parameters:
            return unquoted.decode("utf-8")
    elif "ENCODING=b" in parameters:
        unbased = base64.standard_b64decode(full_name)
        if "CHARSET=UTF-8" in parameters:
            return unbased.decode("utf-8")

    return full_name


def parse_vcard_birthday(date_str: str) -> datetime.date | relativedelta:
    try:
        return datetime.date.fromisoformat(date_str)
    except ValueError:
        if date_str.startswith("--"):
            return relativedelta(
                month=int(date_str[2:4]), day=int(date_str[-2:-4:-1][::-1])
            )
        elif date_str.startswith("0000"):
            return relativedelta(
                month=int(date_str[5:7]), day=int(date_str[-2:-4:-1][::-1])
            )

    raise ValueError(f"Date string '{date_str}' does not match any known format.")


def get_all_birthdays(
    vcf_file: pathlib.Path | str,
    sort_by: typing.Literal[
        "full name", "birthday", "month n day", "next birthday"
    ] = "full name",
):
    with open(vcf_file, "r", encoding="utf-8") as file_in:
        vcards: list[str] = VCARD.findall(file_in.read())

    defined_people: list[tuple[str, datetime.date]] = []
    half_defined_people: list[tuple[str, datetime.date]] = []
    undefined_people: list[str] = []

    for vcard in vcards:
        full_name = FULL_NAME.search(vcard)
        birthday = BIRTHDAY.search(vcard)

        if full_name is not None:
            full_name = resolve_vcard_full_name(full_name)
            if birthday is None:
                undefined_people.append(full_name)
            else:
                birthday = parse_vcard_birthday(birthday.group(1))
                # if birthday > datetime.date.today():
                #     half_defined_people.append((full_name, datetime.date(9999, birthday.month, birthday.day)))
                # else:
                if isinstance(birthday, datetime.date):
                    defined_people.append((full_name, birthday))

    print("All Birthdays 🎂")

    today = datetime.date.today()

    def sort_by_next_birthday(birthday: datetime.date):
        if today.month <= birthday.month and today.day < birthday.day:
            diff = relativedelta(
                datetime.date(today.year, birthday.month, birthday.day), today
            )
        else:
            diff = relativedelta(
                datetime.date(today.year, birthday.month, birthday.day)
                + relativedelta(years=1),
                today,
            )
        return (diff.months, diff.days)

    if sort_by == "full name":
        defined_people.sort(key=lambda x: x[0])
        half_defined_people.sort(key=lambda x: x[0])
    elif sort_by == "birthday":
        defined_people.sort(key=lambda x: x[1])
        half_defined_people.sort(key=lambda x: x[1])
    elif sort_by == "month n day":
        defined_people.sort(key=lambda x: (x[1].month, x[1].day))
        half_defined_people.sort(key=lambda x: (x[1].month, x[1].day))
    elif sort_by == "next birthday":
        defined_people.sort(key=lambda x: sort_by_next_birthday(x[1]))
        half_defined_people.sort(key=lambda x: sort_by_next_birthday(x[1]))

    half_defined_people.sort(key=lambda x: x[0])

    for full_name, birthday in defined_people:
        unique_emoji = birthday_to_emoji(birthday.year, birthday.month, birthday.day)
        if birthday.month == today.month and birthday.day == today.day:
            print(
                f"\n{unique_emoji:<2} Name: {full_name} ({relativedelta(today, birthday).years} y.o.)\n"
                f"Birthday (🥳): {birthday.strftime('%d/%m/%Y')}"
            )
        else:
            if today.month <= birthday.month and today.day < birthday.day:
                diff = relativedelta(
                    datetime.date(today.year, birthday.month, birthday.day), today
                )
            else:
                diff = relativedelta(
                    datetime.date(today.year, birthday.month, birthday.day)
                    + relativedelta(years=1),
                    today,
                )
            months = (
                f" {diff.months} month{'s' if diff.months > 1 else ''}"
                if diff.months > 0
                else ""
            )
            days = (
                f"{' and' if months else ''} {diff.days} day{'s' if diff.days > 1 else ''}"
                if diff.days > 0
                else ""
            )
            print(
                f"\n{unique_emoji:<2} Name: {full_name} ({relativedelta(today, birthday).years} y.o.)\n"
                f"Birthday: {birthday.strftime('%d/%m/%Y')}\n"
                f"Next in{months}{days}"
            )


def get_soon_birthdays(vcf_file: pathlib.Path | str): ...


def vcard_to_json(vcf_file: pathlib.Path | str):
    """
    ```
    [
        {
            "name": str
            "birthday": tuple[int | None, int, int] | None
        }
    ]
    ```
    """


if __name__ == "__main__":
    get_all_birthdays("tests\\untracked\\contacts.vcf", sort_by="next birthday")
