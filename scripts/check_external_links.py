#!/usr/bin/env python3
"""Check Happy ColorPad availability in representative App Store storefronts."""

from __future__ import annotations

import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


APP_ID = 6768400422
APP_NAME = "Happy ColorPad"
STOREFRONTS = {
    "cn": "China",
    "us": "United States",
}
ATTEMPTS = 3
TIMEOUT_SECONDS = 15


def check_app_store_listing(country: str, storefront: str) -> str | None:
    lookup_url = f"https://itunes.apple.com/lookup?id={APP_ID}&country={country}"
    request = Request(
        lookup_url,
        headers={
            "User-Agent": "SinbadLabs-LinkCheck/1.0",
            "Accept": "application/json",
        },
    )
    last_error = "unknown error"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                payload = json.load(response)
                listing = next(
                    (
                        result
                        for result in payload.get("results", [])
                        if result.get("trackId") == APP_ID
                        and result.get("trackName") == APP_NAME
                    ),
                    None,
                )
                if listing is not None:
                    expected_path = f"/{country}/app/"
                    view_url = listing.get("trackViewUrl", "")
                    if expected_path not in view_url or f"id{APP_ID}" not in view_url:
                        last_error = f"unexpected product URL: {view_url}"
                        continue
                    print(
                        f"OK: Apple Lookup returned {APP_NAME} with App ID "
                        f"{APP_ID} for {storefront}"
                    )
                    return None
                last_error = (
                    f"expected {APP_NAME} with App ID {APP_ID}; "
                    f"received {payload.get('resultCount', 0)} result(s)"
                )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = str(error)

        if attempt < ATTEMPTS:
            time.sleep(attempt)

    return f"Apple Lookup for {storefront} ({lookup_url}) failed: {last_error}"


def main() -> int:
    failures = [
        failure
        for country, storefront in STOREFRONTS.items()
        if (failure := check_app_store_listing(country, storefront)) is not None
    ]
    if failures:
        print("Critical external link validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
