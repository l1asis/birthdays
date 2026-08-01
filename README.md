# birthdays

![birthdays GIF demo](https://raw.githubusercontent.com/l1asis/birthdays/refs/heads/main/examples/demo.gif)

[![PyPI Version](https://img.shields.io/pypi/v/birthdays-cli.svg)](https://pypi.org/project/birthdays-cli/)
[![PyPI Python version](https://img.shields.io/pypi/pyversions/birthdays-cli.svg)](https://pypi.org/project/birthdays-cli/)
![PyPI downloads](https://img.shields.io/pypi/dm/birthdays-cli)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

`birthdays` is a robust Python command-line tool designed to conveniently manage, track, and celebrate your contacts' birthdays.

## Features

- **Customizable Sorting:** List birthdays exactly how you want to see them (by upcoming, recent, age, date, (full) name or specific name components like `first_name` and `last_name`).
- **CRUD Operations:** Easily `add`, `edit`, and `delete` entries. The deletion and edit commands feature a convenient fuzzy search so you don't have to type out exact names
- **Smart Imports:** Import contacts directly from `.vcf` vCard files or JSON databases
- **Smart Name Parsing**: Automatically breaks down names into distinct parts, letting you easily verify and adjust them via an interactive prompt.
- **Interactive Merging:** During imports, the CLI intelligently detects duplicates or data collisions and prompts you to safely merge them
- **Leapling Support:** Configure how leap year birthdays (February 29th) are handled in non-leap years, choosing to celebrate either the day before or the day after
- **Organizational Groups:** Assign contacts to custom tags (like `family`, `friends`, or `coworkers`) to keep your database organized and filter terminal outputs.
- **Festive UI:** Every date is assigned a unique, deterministic emoji to keep the terminal vibe bright and colorful *(can be disabled via a global flag or environment variables)*
- **Shell MOTD:** Automatically display a summary of upcoming birthdays when opening a new terminal session, complete with safe, automated hooks for `.bashrc`, `.zshrc`, `config.fish`, and `PowerShell` profiles
- **iCalendar Export:** Generate standard `.ics` files to import into your favorite calendar app, complete with customizable reminders, dynamic text templates, and proper leap year handling.

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

# List sorted alphabetically by last name
birthdays list --sort last_name --order asc

# Temporarily read and display birthdays directly from a file without modifying your local database
birthdays list --file ./contacts.vcf

# Show categorized entries
birthdays list --view groups

# Filter by groups and a condition
birthdays list -g coworkers -g friends --match all
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

> [!TIP]
> The CLI will interactively prompt you to verify the parsed name parts when **adding** / **editing**. To bypass this, append `-y` to automatically accept the parser's result, or provide explicit flags for scripting (e.g., `--first-name "John" --last-name "Doe"`).

### Deleting an Entry

> [!TIP]
> The CLI uses fuzzy matching, so typing a partial name usually works! Append `-y` to skip the confirmation prompt.

```bash
birthdays delete "John Doe"
```

### Deleting Multiple Entries

> [!WARNING]
> This will permanently delete all entries in your database. Use with caution.

```bash
birthdays clear
```

You can also target a specific group to delete, or append `-y` to skip the safety confirmation prompt:

```bash
birthdays clear -g acquaintances
```

```bash
birthdays clear -y
```

### Importing Contacts

> [!TIP]
> The interactive prompt will guide you through any data collisions. Append `-y` to automatically skip these prompts and blindly merge safe entries.

```bash
birthdays import ./contacts.vcf
```

### Shell MOTD (Message of the Day)

You can automatically display a minimal summary of upcoming birthdays every time you open a new terminal session.

**Display the MOTD manually:**

```bash
birthdays motd
```

**Enable the startup hook:**

```bash
birthdays motd enable --days 14 --limit 5 --quiet-if-empty --once-per-day
```

This automatically detects your shell and injects an easily removable sentinel block. Running this command again with new flags will update the existing block in-place. The `--once-per-day` flag ensures the summary is only printed the first time you open a terminal each day, preventing terminal spam.

> [!NOTE]
> You can pass a `--rc-file` flag if you use a custom shell config.

**Disable the startup hook:**

```bash
birthdays motd disable
```

This safely removes the MOTD sentinel block from your shell configuration without affecting surrounding custom code.

### Database Maintenance

> [!NOTE]
> If you are upgrading from an older version of `birthdays`, your existing entries won't have the new structured name components. You can backfill them automatically.

**Repair and backfill missing name parts:**

```bash
birthdays repair --names
```

**Force a complete resync of all name parts from their full names:**

```bash
birthdays repair --names --force
```

Here are the additions to include in your README to document the new export feature.

Add this bullet point to the `## Features` section:

```md
- **iCalendar Export:** Generate standard `.ics` files to import into your favorite calendar app, complete with customizable reminders, dynamic text templates, and proper leap year handling.

```

### Exporting to iCalendar (.ics)

**Basic static export (creates infinite recurring events):**

```bash
birthdays export ./my_birthdays.ics
```

**Advanced spanned export (generates distinct events for the next 10 years to support dynamic ages):**

```bash
birthdays export ./my_birthdays.ics --years 10
```

**Customize reminders, templates, and filter by groups:**

```bash
birthdays export ./family.ics -g family --alarm-days 2 --alarm-time "10:00" --title "{first_name}'s {ordinal_age} Birthday!"
```

## Configurations

### Database Path

By default, `birthdays` stores your `birthdays.json` database in your operating system's standard user data directory. If you want to use a custom location (for example, to sync your database via Dropbox, Nextcloud, or a dotfiles repository), you can override this behavior by setting the `BIRTHDAYS_HOME` environment variable.

- `BIRTHDAYS_HOME=/path/to/your/custom/folder`

The tool will automatically create the directory and the `birthdays.json` file inside it if they do not already exist.

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
