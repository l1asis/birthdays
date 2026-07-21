from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("birthdays-cli")
except PackageNotFoundError:
    __version__ = "unknown"

__about__ = rf"""
                           🔥
                    🔥     /^\    🔥
                  __/^\____|_|____/^\__
                 /  |_|           |_|  \
                 \_____________________/
                 |  . . . . . . . . .  |
                 | -~-~-~-~-~-~-~-~-~- |
                 | ~-~-~-~-~-~-~-~-~-~ |
                 *_____________________*

  birthdays: Your birthday list is in your hands only.
  ----------------------------------------------------------
  Version:      {__version__}
  Author:       Volodymyr Horshenin (@l1asis)
  License:      MIT
  Repository:   https://github.com/l1asis/birthdays

  Description: 
  A command-line utility for displaying and managing birthdays
  from JSON- or vCard-based contacts.

  Usage:
  Run `python -m birthdays-cli --help` to see available commands.
"""
