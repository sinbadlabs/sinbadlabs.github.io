#!/usr/bin/env python3
"""Check the small set of external URLs that are critical to the product."""

from __future__ import annotations

import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CRITICAL_URLS = {
    "ColorPad TestFlight beta": {
        "url": "https://testflight.apple.com/join/a78YM2ew",
        "required_markers": ("Happy ColorPad", "beta"),
    },
}
ATTEMPTS = 3
TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 128 * 1024


def check_url(name: str, url: str, required_markers: tuple[str, ...]) -> str | None:
    request = Request(
        url,
        headers={
            "User-Agent": "SinbadLabs-LinkCheck/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    last_error = "unknown error"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                status = response.status
                if 200 <= status < 400:
                    charset = response.headers.get_content_charset() or "utf-8"
                    body = response.read(MAX_RESPONSE_BYTES).decode(
                        charset, errors="replace"
                    )
                    folded_body = body.casefold()
                    missing_markers = [
                        marker
                        for marker in required_markers
                        if marker.casefold() not in folded_body
                    ]
                    if not missing_markers:
                        print(
                            f"OK: {name} returned HTTP {status} "
                            "with the expected page content"
                        )
                        return None
                    last_error = (
                        "response did not contain expected markers: "
                        + ", ".join(missing_markers)
                    )
                else:
                    last_error = f"HTTP {status}"
        except HTTPError as error:
            last_error = f"HTTP {error.code}"
        except (URLError, TimeoutError) as error:
            last_error = str(error)

        if attempt < ATTEMPTS:
            time.sleep(attempt)

    return f"{name} ({url}) failed after {ATTEMPTS} attempts: {last_error}"


def main() -> int:
    failures = [
        failure
        for name, check in CRITICAL_URLS.items()
        if (
            failure := check_url(
                name,
                check["url"],
                check["required_markers"],
            )
        )
        is not None
    ]
    if failures:
        print("Critical external link validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
