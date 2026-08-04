#!/usr/bin/env python3
"""Validate local links, assets, fragments, and basic HTML page structure."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_SCHEMES = {"http", "https", "mailto", "tel"}
LEGAL_DUPLICATES = {
    ROOT / "privacy/colorpad.html": ROOT / "colorpad/privacy/index.html",
    ROOT / "terms/colorpad.html": ROOT / "colorpad/terms/index.html",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []
        self.ids: set[str] = set()
        self.h1_count = 0
        self.has_title = False
        self.has_viewport = False
        self.language: str | None = None
        self.text_parts: list[str] = []
        self.canonical_url: str | None = None
        self.meta_description: str | None = None
        self.navigation_links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)

        if tag == "html":
            self.language = attributes.get("lang")
        elif tag == "title":
            self.has_title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta":
            if attributes.get("name", "").lower() == "viewport":
                self.has_viewport = True
            if attributes.get("name", "").lower() == "description":
                self.meta_description = attributes.get("content")
            if attributes.get("http-equiv", "").lower() == "refresh":
                content = attributes.get("content", "")
                match = re.search(r"url\s*=\s*([^;]+)", content, re.IGNORECASE)
                if match:
                    self.references.append(match.group(1).strip(" '\""))

        if tag == "link":
            relationships = set(attributes.get("rel", "").lower().split())
            if "canonical" in relationships:
                self.canonical_url = attributes.get("href")
        elif tag == "a" and attributes.get("href"):
            self.navigation_links.append(attributes["href"])

        for attribute in ("href", "src"):
            value = attributes.get(attribute)
            if value:
                self.references.append(value)

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.text_parts.append(text)


def local_target(source: Path, reference: str) -> tuple[Path, str] | None:
    parsed = urlparse(reference)
    if parsed.scheme in EXTERNAL_SCHEMES or reference.startswith("//"):
        return None

    raw_path = unquote(parsed.path)
    if not raw_path:
        target = source
    elif raw_path.startswith("/"):
        target = ROOT / raw_path.lstrip("/")
    else:
        target = source.parent / raw_path

    if raw_path.endswith("/") or target.is_dir():
        target /= "index.html"
    return target.resolve(), unquote(parsed.fragment)


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def visible_text(parser: PageParser) -> str:
    return " ".join(" ".join(parser.text_parts).split())


def main() -> int:
    pages = sorted(ROOT.rglob("*.html"))
    parsed_pages = {page.resolve(): parse_page(page) for page in pages}
    errors: list[str] = []

    for page, parser in parsed_pages.items():
        label = page.relative_to(ROOT)
        if not parser.language:
            errors.append(f"{label}: missing html lang attribute")
        if not parser.has_title:
            errors.append(f"{label}: missing title")
        if not parser.has_viewport:
            errors.append(f"{label}: missing viewport meta tag")
        if parser.h1_count != 1:
            errors.append(f"{label}: expected one h1, found {parser.h1_count}")

        for reference in parser.references:
            resolved = local_target(page, reference)
            if resolved is None:
                continue
            target, fragment = resolved
            if not target.is_file():
                errors.append(f"{label}: {reference!r} points to missing {target}")
                continue
            if fragment and target.suffix.lower() == ".html":
                target_parser = parsed_pages.get(target)
                if target_parser is None or fragment not in target_parser.ids:
                    errors.append(f"{label}: {reference!r} points to missing fragment")

    for legacy, canonical in LEGAL_DUPLICATES.items():
        legacy_parser = parsed_pages.get(legacy.resolve())
        canonical_parser = parsed_pages.get(canonical.resolve())
        if legacy_parser is None or canonical_parser is None:
            errors.append(f"missing legal page pair: {legacy} and {canonical}")
        else:
            parity_checks = {
                "visible text": (
                    visible_text(legacy_parser),
                    visible_text(canonical_parser),
                ),
                "canonical URL": (
                    legacy_parser.canonical_url,
                    canonical_parser.canonical_url,
                ),
                "meta description": (
                    legacy_parser.meta_description,
                    canonical_parser.meta_description,
                ),
                "navigation and contact links": (
                    legacy_parser.navigation_links,
                    canonical_parser.navigation_links,
                ),
            }
            for field, (legacy_value, canonical_value) in parity_checks.items():
                if legacy_value != canonical_value:
                    errors.append(
                        f"{legacy.relative_to(ROOT)} {field} differs from "
                        f"{canonical.relative_to(ROOT)}"
                    )

    if errors:
        print("Site validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Validated {len(pages)} HTML pages: local links and structure are OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
