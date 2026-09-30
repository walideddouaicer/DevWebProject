"""Build static/icons/sprite.svg from the Lucide icons listed in static/icons/icons.txt.

    .venv/bin/python scripts/build_icons.py

Source SVGs are cached in scripts/vendor/lucide/ (committed, ISC license) so the build
works offline; missing ones are fetched from jsdelivr (lucide-static).
"""

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "vendor" / "lucide"
LIST = ROOT / "static" / "icons" / "icons.txt"
OUT = ROOT / "static" / "icons" / "sprite.svg"
CDN = "https://cdn.jsdelivr.net/npm/lucide-static@0/icons/{}.svg"


def source(name):
    path = CACHE / f"{name}.svg"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(CDN.format(name), timeout=20) as response:
            path.write_bytes(response.read())
    return path.read_text()


names = [
    line.strip()
    for line in LIST.read_text().splitlines()
    if line.strip() and not line.startswith("#")
]
symbols, missing = [], []
for name in names:
    try:
        svg = source(name)
    except Exception:
        missing.append(name)
        continue
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    inner = re.sub(r"<!--.*?-->", "", inner, flags=re.S)
    inner = re.sub(r"\s+", " ", inner).strip()
    symbols.append(
        f'<symbol id="i-{name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{inner}</symbol>'
    )

OUT.write_text('<svg xmlns="http://www.w3.org/2000/svg">' + "".join(symbols) + "</svg>\n")
print(f"{len(symbols)} icons -> {OUT.relative_to(ROOT)}")
if missing:
    sys.exit(f"missing: {', '.join(missing)}")
