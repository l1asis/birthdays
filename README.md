# birthdays

![birthdays GIF demo](https://raw.githubusercontent.com/l1asis/birthdays/refs/heads/main/examples/demo.gif)

[![PyPI Version](https://img.shields.io/pypi/v/birthdays-cli.svg)](https://pypi.org/project/birthdays-cli/)
[![PyPI Python version](https://img.shields.io/pypi/pyversions/birthdays-cli.svg)](https://pypi.org/project/birthdays-cli/)
![PyPI downloads](https://img.shields.io/pypi/dm/birthdays-cli)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

`birthdays` is a robust Python command-line tool designed to conveniently manage, track, and celebrate your contacts' birthdays.

## Features

- **Customizable Sorting:** List birthdays exactly how you want to see them (by upcoming, recent, age, name, or date)
- **CRUD Operations:** Easily `add`, `edit`, and `delete` entries. The deletion and edit commands feature a convenient fuzzy search so you don't have to type out exact names
- **Smart Imports:** Import contacts directly from `.vcf` vCard files or JSON databases
- **Interactive Merging:** During imports, the CLI intelligently detects duplicates or data collisions and prompts you to safely merge them
- **Leapling Support:** Configure how leap year birthdays (February 29th) are handled in non-leap years, choosing to celebrate either the day before or the day after
- **Festive UI:** Every date is assigned a unique, deterministic emoji to keep the terminal vibe bright and colorful *(can be disabled via a global flag or environment variables)*
- **Shell MOTD:** Automatically display a summary of upcoming birthdays when opening a new terminal session, complete with safe, automated hooks for `.bashrc`, `.zshrc`, `config.fish`, and `PowerShell` profiles.

## Requirements

- Python 3.11+

## Installation

Install the package from PyPI using your favorite package management tool such as pip, pipx, or uv:

```bash
pip install birthdays-cli
```

Or install the latest version from source:

```bash
git clone https://github.com/l1asis/birthdays.git
cd birthdays
pip install .
```

## Usage

`birthdays` uses simple subcommands to organize different operations. You can append `--help` to any command to see its available arguments.

### Listing Birthdays

> [!NOTE]
> By default, this sorts by upcoming birthdays in descending order so the most immediate celebrations are right at your cursor.

```bash
# Basic list
birthdays list

# List sorted by age in ascending order
birthdays list --sort age --order asc

# Temporarily read and display birthdays directly from a file without modifying your local database
birthdays list --file ./contacts.vcf
```

### Adding an Entry

> [!NOTE]
> The date can be formatted as `YYYY-MM-DD`, or simply `MM-DD` if the year is unknown.

```bash
birthdays add "John Doe" 1990-05-14 --note "Loves chocolate cake"
```

### Editing an Entry

> [!NOTE]
> You can use either the name or UUID. You only need to pass the flags for the specific data you want to change.

```bash
birthdays edit "John Doe" --date 1991-05-14
```

### Deleting an Entry

> [!TIP]
> The CLI uses fuzzy matching, so typing a partial name usually works! Append `-y` to skip the confirmation prompt.

```bash
birthdays delete "John Doe"
```

### Importing Contacts

> [!TIP]
> The interactive prompt will guide you through any data collisions. Append `-y` to automatically skip these prompts and blindly merge safe entries.

```bash
birthdays import ./contacts.vcf
```

### Shell MOTD (Message of the Day)

> [!TIP]
> You can automatically display a minimal summary of upcoming birthdays every time you open a new terminal session.

**Display the MOTD manually:**

```bash
birthdays motd
```

**Enable the startup hook:**

```bash
birthdays motd enable --days 14 --limit 5 --quiet-if-empty
```

This automatically detects your shell and injects an easily removable sentinel block. Running this command again with new flags will update the existing block in-place.

> [!NOTE]
> You can pass a `--rc-file` flag if you use a custom shell config.

**Disable the startup hook:**

```bash
birthdays motd disable
```

This safely removes the MOTD sentinel block from your shell configuration without affecting surrounding custom code.

## Configurations

### Emojis

You can disable emojis globally across all subcommands by placing the `--no-emoji` flag *before* the subcommand (e.g., `birthdays --no-emoji list`).

For a more permanent solution, `birthdays` respects the following environment variables:

- `BIRTHDAYS_NO_EMOJI=1` (or `true`, `yes`)
- `NO_EMOJI=1` (the widely adopted community convention)

> [!NOTE]
> The method for setting environment variables depends on your operating system and terminal. Please search online for instructions specific to your OS.

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feat/amazing-feature`)
3. Commit your Changes (`git commit -m 'feat: ✨ add some amazing-feature'`)
4. Push to the Branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.
