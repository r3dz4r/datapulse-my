#!/usr/bin/env python3
"""Read the newest publication-cell date from HTML listing rows."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path


def normalized_date(value: str) -> str | None:
    """Normalize the date formats accepted by the existing browser date rule."""
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value).isoformat()
        match = re.fullmatch(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", value)
        if match:
            day, month, year = map(int, match.groups())
            return date(year, month, day).isoformat()
    except ValueError:
        pass
    return None


class ListingDates(HTMLParser):
    """Keep only the first valid date in each marked row's publication cell."""

    def __init__(self, row_attribute: str, date_cell_index: int, date_pattern: str) -> None:
        super().__init__(convert_charrefs=True)
        self.row_attribute = row_attribute
        self.date_cell_index = date_cell_index
        self.pattern = re.compile(date_pattern)
        self.in_row = False
        self.in_date_cell = False
        self.cell_index = -1
        self.cell_text: list[str] = []
        self.dates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr" and any(name == self.row_attribute for name, _ in attrs):
            self.in_row = True
            self.cell_index = -1
            self.cell_text = []
        elif tag == "td" and self.in_row:
            self.cell_index += 1
            self.in_date_cell = self.cell_index == self.date_cell_index

    def handle_data(self, data: str) -> None:
        if self.in_date_cell:
            self.cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self.in_date_cell = False
        if tag != "tr" or not self.in_row:
            return
        for match in self.pattern.finditer(" ".join(self.cell_text)):
            parsed = normalized_date(match.group())
            if parsed is not None:
                self.dates.append(parsed)
                break
        self.in_row = False


def extract_date(path: Path, row_attribute: str, date_cell_index: int, date_pattern: str) -> str:
    """Return the newest publication date, or an empty string if none exists."""
    parser = ListingDates(row_attribute, date_cell_index, date_pattern)
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return max(parser.dates, default="")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row-attribute", required=True)
    parser.add_argument("--date-cell-index", required=True, type=int)
    parser.add_argument("--date-pattern", required=True)
    parser.add_argument("html_file", type=Path)
    args = parser.parse_args()
    sys.stdout.write(extract_date(args.html_file, args.row_attribute, args.date_cell_index, args.date_pattern) + "\n")


if __name__ == "__main__":
    main()
