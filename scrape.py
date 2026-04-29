#!/usr/bin/env python3
"""Download NASA "Your Name in Landsat" alphabet image variants."""

from __future__ import annotations

import string
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://science.nasa.gov/specials/your-name-in-landsat/images"
OUTPUT_DIR = Path("assets/landsat-letters")
MAX_VARIANTS = 99
MISS_LIMIT = 1
TIMEOUT = 20


def fetch(url: str) -> bytes | None:
    request = Request(url, headers={"User-Agent": "nasa-landsatify/1.0"})

    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                return None
            return response.read()
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except URLError as exc:
        raise RuntimeError(f"Could not download {url}: {exc.reason}") from exc


def download_letter(letter: str) -> list[Path]:
    saved: list[Path] = []
    misses = 0
    letter_dir = OUTPUT_DIR / letter
    letter_dir.mkdir(parents=True, exist_ok=True)

    for variant in range(0, MAX_VARIANTS + 1):
        source_filename = f"{letter}_{variant}.jpg"
        target = letter_dir / f"{variant}.jpg"

        if target.exists():
            saved.append(target)
            misses = 0
            continue

        url = f"{BASE_URL}/{source_filename}"
        image = fetch(url)

        if image is None:
            misses += 1
            if misses >= MISS_LIMIT:
                break
            continue

        target.write_bytes(image)
        saved.append(target)
        misses = 0

    return saved


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0

    for letter in string.ascii_lowercase:
        files = download_letter(letter)
        total += len(files)
        names = ", ".join(path.name for path in files) or "none"
        print(f"{letter.upper()}: {len(files)} file(s) - {names}")

    print(f"\nSaved {total} file(s) in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
