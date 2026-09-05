#!/usr/bin/env python3
"""Small, deterministic parsers for the legacy ST MyEnergyStats protocol."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode, urljoin, urlparse


ST_BASE_URL = "https://meih.st.gov.my/statistics"
ST_REPORT_PATH = "/STOASPublicPortlet/energystatistic/searchStatistic.oas"


@dataclass
class Link:
    href: str
    text: str


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[Link] = []
        self._link_href: str | None = None
        self._link_text: list[str] = []
        self.form_action: str | None = None
        self.in_form = False
        self.inputs: list[tuple[str, str, str]] = []
        self.select_name: str | None = None
        self.select_options: dict[str, list[str]] = {}
        self.select_value: dict[str, str] = {}
        self._option_value: str | None = None
        self._option_text: list[str] = []
        self._option_selected = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "a":
            self._link_href, self._link_text = attr.get("href"), []
        if tag == "form" and attr.get("id") == "parameterForm":
            self.in_form, self.form_action = True, attr.get("action")
        if self.in_form and tag == "input" and attr.get("name"):
            self.inputs.append((attr["name"], attr.get("value", ""), attr.get("type", "text")))
        if self.in_form and tag == "select" and attr.get("name"):
            self.select_name = attr["name"]
            self.select_options.setdefault(self.select_name, [])
        if self.in_form and tag == "option" and self.select_name:
            self._option_value, self._option_text = attr.get("value", ""), []
            self._option_selected = "selected" in attr

    def handle_data(self, data: str) -> None:
        if self._link_href is not None:
            self._link_text.append(data)
        if self._option_value is not None:
            self._option_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link_href is not None:
            self.links.append(Link(self._link_href, "".join(self._link_text).strip()))
            self._link_href = None
        if tag == "option" and self.select_name and self._option_value is not None:
            self.select_options[self.select_name].append(self._option_value)
            if self._option_selected or self.select_name not in self.select_value:
                self.select_value[self.select_name] = self._option_value
            self._option_value = None
        if tag == "select":
            self.select_name = None
        if tag == "form" and self.in_form:
            self.in_form = False


def _parse(text: str) -> _DocumentParser:
    parser = _DocumentParser()
    parser.feed(text)
    return parser


def _normalise_href(href: str) -> str:
    # Liferay renders a space before portlet query parameters in this legacy UI.
    return re.sub(r"\s+(_Eng_Statistic_WAR_)", r"&\1", html.unescape(href)).strip()


def approved_url(url: str, *, allow_report: bool = False, allow_download: bool = False) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "meih.st.gov.my":
        return False
    if parsed.path == "/statistics" or parsed.path.startswith("/statistics;"):
        return True
    if allow_report and parsed.path == ST_REPORT_PATH:
        return True
    return allow_download and parsed.path == "/STOASPublicPortlet/energystatistic/downloadElcFile.oas"


def find_detail_url(base_html: str, event_id: str, flow_id: str) -> str | None:
    for link in _parse(base_html).links:
        href = _normalise_href(link.href)
        candidate = urljoin(ST_BASE_URL, href)
        if event_id in candidate and re.search(rf"(?:[?&])flowId={re.escape(flow_id)}(?:&|$)", candidate):
            if approved_url(candidate):
                return candidate
    return None


def form_request(detail_html: str, group_by: str | None, group_value: str | None, select_all: str | None) -> tuple[str, str] | None:
    document = _parse(detail_html)
    if not document.in_form and not document.inputs:
        return None
    action = urljoin(ST_BASE_URL, document.form_action or ST_REPORT_PATH)
    if not approved_url(action, allow_report=True):
        return None
    values: list[tuple[str, str]] = []
    for name, value, kind in document.inputs:
        if kind.lower() not in {"submit", "button", "image", "reset"}:
            values.append((name, value))
    for name, value in document.select_value.items():
        if name != group_by and name != select_all:
            values.append((name, value))
    if group_by and group_value:
        values.append(("optionBy", "1" if group_by == "region" else "2"))
        values.append((group_by, group_value))
    if select_all:
        options = document.select_options.get(select_all, [])
        if not options:
            # The production form uses hidden allProducts fields; retaining them
            # is sufficient when no selectable control is present.
            hidden = [value for name, value, _ in document.inputs if name == f"all{select_all.title()}" or name == select_all]
            if hidden:
                return action, urlencode(values)
        if not options:
            return None
        values.extend((select_all, value) for value in options)
    return action, urlencode(values)


def latest_table_year(report_html: str) -> tuple[int | None, int, int]:
    years = [int(value) for value in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", report_html)]
    current_year = __import__("datetime").date.today().year
    years = [year for year in years if 1900 <= year <= current_year]
    rows = len(re.findall(r"<tr\b", report_html, flags=re.I))
    columns = max((len(re.findall(r"<t[dh]\b", row, flags=re.I)) for row in re.findall(r"<tr\b.*?</tr\s*>", report_html, flags=re.I | re.S)), default=0)
    return (max(years) if years else None), max(rows - 1, 0), columns


def latest_pdf_link(detail_html: str) -> tuple[str, int] | None:
    current_year = __import__("datetime").date.today().year
    candidates: list[tuple[int, str]] = []
    for link in _parse(detail_html).links:
        href = urljoin(ST_BASE_URL, _normalise_href(link.href))
        if not approved_url(href, allow_download=True):
            continue
        years = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", link.text + " " + href)
        for value in years:
            year = int(value)
            if 1900 <= year <= current_year:
                candidates.append((year, href))
    return max(candidates, default=None)


def _main(argv: Iterable[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["detail-url", "form-request", "table-metrics", "pdf-link"])
    parser.add_argument("file", type=Path)
    parser.add_argument("--event-id")
    parser.add_argument("--flow-id")
    parser.add_argument("--group-by")
    parser.add_argument("--group-value")
    parser.add_argument("--select-all-field")
    args = parser.parse_args(list(argv))
    body = args.file.read_text(encoding="utf-8", errors="replace")
    if args.command == "detail-url":
        value = find_detail_url(body, args.event_id or "", args.flow_id or "")
        if value:
            print(value)
            return 0
    elif args.command == "form-request":
        value = form_request(body, args.group_by, args.group_value, args.select_all_field)
        if value:
            print("\t".join(value))
            return 0
    elif args.command == "table-metrics":
        year, rows, columns = latest_table_year(body)
        print(json.dumps({"year": year, "record_count": rows, "column_count": columns}, sort_keys=True, separators=(",", ":")))
        return 0 if year else 1
    else:
        value = latest_pdf_link(body)
        if value:
            print(f"{value[0]}\t{value[1]}")
            return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
