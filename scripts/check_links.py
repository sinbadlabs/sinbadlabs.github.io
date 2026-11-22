#!/usr/bin/env python3
"""Validate local links, assets, fragments, and basic HTML page structure."""

from __future__ import annotations

import re
import sys
from argparse import ArgumentParser
from collections import Counter
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path
from unicodedata import normalize
from urllib.parse import quote, unquote, urlparse
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent.parent
SITE_ORIGIN = "https://sinbadlabs.com"
SITEMAP_NAMESPACE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
URL_PATH_DELIMITERS = "/!$&'()*+,;=:@"
EXTERNAL_SCHEMES = {"data", "http", "https", "mailto", "tel"}
LEGAL_DUPLICATES = {
    ROOT / "privacy/colorpad.html": ROOT / "colorpad/privacy/index.html",
    ROOT / "terms/colorpad.html": ROOT / "colorpad/terms/index.html",
}
PRODUCT = ROOT / "colorpad/index.html"
SUPPORT = ROOT / "colorpad/support/index.html"
GUIDES = ROOT / "colorpad/guides"
GUIDE_INDEX = GUIDES / "index.html"
IMPORT_GUIDE = GUIDES / "color-your-own-coloring-pages-on-ipad/index.html"
FOCUS_GUIDE = GUIDES / "make-the-main-subject-stand-out/index.html"
GUIDE_IMAGES = GUIDES / "images"
BUNNY_PRACTICE_PNG = GUIDE_IMAGES / "bunny-coloring-page.png"
SKY_COMPARISON_IMAGES = ("bunny-medium-sky.webp", "bunny-light-sky.webp")
REQUIRED_GUIDE_IMAGES = {
    IMPORT_GUIDE: {
        None: (
            "bunny-coloring-page.webp",
            "ipad-bunny-canvas.webp",
            "ipad-photos-picker.webp",
            "ipad-bunny-saved.webp",
        ),
    },
    FOCUS_GUIDE: {
        "compare": SKY_COMPARISON_IMAGES,
        "check-values": SKY_COMPARISON_IMAGES,
        None: ("ipad-bunny-light-sky.webp",),
    },
}
REQUIRED_GUIDE_DOWNLOADS = {
    IMPORT_GUIDE: BUNNY_PRACTICE_PNG,
    FOCUS_GUIDE: BUNNY_PRACTICE_PNG,
}
REQUIRED_GUIDE_LINKS = {
    (PRODUCT, "coloring-guides"): (IMPORT_GUIDE, FOCUS_GUIDE),
    (PRODUCT, "import-your-own-pictures"): (IMPORT_GUIDE,),
    (PRODUCT, "links"): (GUIDE_INDEX,),
    (SUPPORT, "import-a-coloring-page"): (IMPORT_GUIDE,),
    (GUIDE_INDEX, None): (IMPORT_GUIDE, FOCUS_GUIDE, PRODUCT, SUPPORT),
    (IMPORT_GUIDE, None): (GUIDE_INDEX, FOCUS_GUIDE, PRODUCT, SUPPORT),
    (FOCUS_GUIDE, None): (GUIDE_INDEX, IMPORT_GUIDE, PRODUCT, SUPPORT),
}
CONTENT_CONTAINERS = {"article", "nav", "section"}


def srcset_urls(value: str) -> Iterator[str]:
    """Read URLs and skip optional width or density descriptors."""
    separators = " \t\n\f\r,"
    remaining = value.lstrip(separators)
    while remaining:
        tokens = re.split(r"[ \t\n\f\r]+", remaining, maxsplit=1)
        url = tokens[0]
        # A comma inside the URL is part of the URL. A trailing comma ends the candidate.
        yield url.rstrip(",")
        remaining = tokens[1] if len(tokens) == 2 else ""
        if not url.endswith(","):
            remaining = remaining.partition(",")[2]
        remaining = remaining.lstrip(separators)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []
        self.ids: set[str] = set()
        self.h1_count = 0
        self.in_title = False
        self.title_parts: list[str] = []
        self.has_viewport = False
        self.language: str | None = None
        self.text_parts: list[str] = []
        self.canonical_urls: list[str | None] = []
        self.blocks_indexing = False
        self.meta_description: str | None = None
        self.navigation_links: list[str] = []
        self.download_links: list[str] = []
        self.links_by_container: dict[str, list[str]] = {}
        self.containers: list[tuple[str, str | None]] = []
        self.images: list[tuple[str | None, str | None]] = []
        self.image_sources_by_container: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)
        if tag in CONTENT_CONTAINERS:
            self.containers.append((tag, element_id))

        if tag == "html":
            self.language = attributes.get("lang")
        elif tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta":
            name = (attributes.get("name") or "").strip().lower()
            if name == "viewport":
                self.has_viewport = True
            elif name == "description":
                self.meta_description = attributes.get("content")
            elif name in {"robots", "googlebot"}:
                directives = re.split(r"[\s,]+", (attributes.get("content") or "").lower())
                if {"noindex", "none"}.intersection(directives):
                    self.blocks_indexing = True
            if attributes.get("http-equiv", "").lower() == "refresh":
                content = attributes.get("content", "")
                match = re.search(r"url\s*=\s*([^;]+)", content, re.IGNORECASE)
                if match:
                    self.references.append(match.group(1).strip(" '\""))

        if tag == "link":
            relationships = set(attributes.get("rel", "").lower().split())
            if "canonical" in relationships:
                self.canonical_urls.append(attributes.get("href"))
        elif tag == "a" and attributes.get("href"):
            href = attributes["href"]
            self.navigation_links.append(href)
            if "download" in attributes:
                self.download_links.append(href)
            for _, container_id in self.containers:
                if container_id:
                    self.links_by_container.setdefault(container_id, []).append(href)
        elif tag == "img":
            src = attributes.get("src")
            self.images.append((src, attributes.get("alt")))
            if src:
                for _, container_id in self.containers:
                    if container_id:
                        self.image_sources_by_container.setdefault(container_id, []).append(src)

        for attribute in ("href", "src"):
            value = attributes.get(attribute)
            if value:
                self.references.append(value)

        if tag in {"img", "source"} and (srcset := attributes.get("srcset")):
            self.references.extend(srcset_urls(srcset))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if self.containers and self.containers[-1][0] == tag:
            self.containers.pop()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
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


def public_url(page: Path, site_root: Path) -> str:
    path = page.relative_to(site_root).as_posix()
    if page.name == "index.html":
        path = path.removesuffix("index.html")
    encoded_path = quote(normalize("NFC", path), safe=URL_PATH_DELIMITERS)
    return f"{SITE_ORIGIN}/{encoded_path}"


def validate_sitemap(path: Path, errors: list[str]) -> None:
    try:
        sitemap = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as error:
        errors.append(f"{path}: {error}")
        return

    if sitemap.tag != f"{SITEMAP_NAMESPACE}urlset":
        errors.append(f"{path}: expected a sitemap urlset")
        return

    sitemap_urls = Counter(
        loc.text or "" for loc in sitemap.findall(f"{SITEMAP_NAMESPACE}url/{SITEMAP_NAMESPACE}loc")
    )
    canonical_urls = set()
    noindex_urls = set()
    site_root = path.parent
    for page in site_root.rglob("*.html"):
        url = public_url(page, site_root)
        parser = parse_page(page)
        if parser.blocks_indexing:
            noindex_urls.add(url)
        elif parser.canonical_urls == [url]:
            canonical_urls.add(url)
    for url in sorted(canonical_urls):
        if sitemap_urls[url] != 1:
            errors.append(f"{path}: expected one entry for {url}")
    for url in sorted(sitemap_urls.keys() - canonical_urls):
        if url in noindex_urls:
            errors.append(f"{path}: exclude noindex URL {url} with sitemap: false in its front matter")
        else:
            errors.append(f"{path}: unexpected URL {url!r}")


def validate_guides(parsed_pages: dict[Path, PageParser], errors: list[str]) -> None:
    titles: set[str] = set()
    descriptions: set[str] = set()
    for page, parser in parsed_pages.items():
        if GUIDES not in page.parents:
            continue
        label = page.relative_to(ROOT)
        expected_url = public_url(page, ROOT)
        if parser.canonical_urls != [expected_url]:
            errors.append(f"{label}: expected one canonical URL matching {expected_url}")
        title = " ".join("".join(parser.title_parts).split()).casefold()
        description = " ".join((parser.meta_description or "").split()).casefold()
        if title in titles:
            errors.append(f"{label}: guide title must be unique")
        if not description or description in descriptions:
            errors.append(f"{label}: guide meta description must be nonempty and unique")
        titles.add(title)
        descriptions.add(description)

        # The guide illustrations are part of the instructions.
        for src, alt in parser.images:
            if not alt or not alt.strip():
                errors.append(f"{label}: image {src!r} needs descriptive alt text")

        for container, filenames in REQUIRED_GUIDE_IMAGES.get(page, {}).items():
            sources = (
                parser.image_sources_by_container.get(container, [])
                if container
                else [src for src, _ in parser.images if src]
            )
            image_targets = {
                resolved[0]
                for src in sources
                if (resolved := local_target(page, src))
            }
            location = f"{label}#{container}" if container else str(label)
            for filename in filenames:
                if GUIDE_IMAGES / filename not in image_targets:
                    errors.append(f"{location}: missing required image {filename}")

        required_download = REQUIRED_GUIDE_DOWNLOADS.get(page)
        if required_download is not None:
            download_targets = {
                resolved[0] for href in parser.download_links if (resolved := local_target(page, href))
            }
            if required_download not in download_targets:
                errors.append(f"{label}: missing download link for {required_download.name}")

    for (source, container), targets in REQUIRED_GUIDE_LINKS.items():
        parser = parsed_pages.get(source)
        label = source.relative_to(ROOT)
        if parser is None:
            errors.append(f"{label}: missing page with required guide links")
            continue
        links = parser.links_by_container.get(container, []) if container else parser.navigation_links
        destinations = {
            resolved[0] for link in links if (resolved := local_target(source, link))
        }
        location = f"{label}#{container}" if container else str(label)
        for target in targets:
            if target not in destinations:
                errors.append(f"{location}: missing link to {target.relative_to(ROOT)}")


def main() -> int:
    arguments = ArgumentParser(description=__doc__)
    arguments.add_argument("--sitemap", type=Path, help="Path to the built sitemap.xml")
    args = arguments.parse_args()

    pages = sorted(
        path
        for path in ROOT.rglob("*.html")
        if not {"node_modules", "_site"}.intersection(path.relative_to(ROOT).parts)
    )
    parsed_pages = {page.resolve(): parse_page(page) for page in pages}
    errors: list[str] = []

    for page, parser in parsed_pages.items():
        label = page.relative_to(ROOT)
        if not parser.language:
            errors.append(f"{label}: missing html lang attribute")
        if not "".join(parser.title_parts).strip():
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
                    legacy_parser.canonical_urls,
                    canonical_parser.canonical_urls,
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

    validate_guides(parsed_pages, errors)
    if args.sitemap is not None:
        validate_sitemap(args.sitemap, errors)

    if errors:
        print("Site validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Validated {len(pages)} HTML pages: links, structure, and guide checks are OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
