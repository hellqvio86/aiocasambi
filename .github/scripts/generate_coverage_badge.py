#!/usr/bin/env python3
"""Generate a dynamic coverage badge SVG from coverage data.

Extracts coverage percentage from coverage.json (or .coverage) and generates
a coverage.svg badge via shields.io (with offline fallback).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

PYTEST_ICON_B64 = (
    "PHN2ZyBmaWxsPSJ3aGl0ZSIgcm9sZT0iaW1nIiB2aWV3Qm94PSIwIDAgMjQgMjQiIHhtbG5zPSJodHRwOi8vd3d3Lncz"
    "Lm9yZy8yMDAwL3N2ZyI+PHRpdGxlPlB5dGVzdDwvdGl0bGU+PHBhdGggZD0iTTIuNjE1MiAwdi44ODY3aDMuODM5OVYw"
    "em01LjAyMTUgMHYuODg2N2gzLjg0MThWMHptNC45NTcgMHYuODg2N2gzLjg0MThWMHptNC45MzU2IDB2Ljg4NjdoMy44"
    "NDE4VjB6TTIuNDQ3MyAxLjg5NDVhLjkzNS45MzUgMCAwIDAtLjkzNTYuOTM1NmMwIC41MTcuNDE4NS45Mzc1LjkzNTYu"
    "OTM3NWgxOS4xMDU0Yy41MTcxIDAgLjkzNTYtLjQyMDQuOTM1Ni0uOTM3NWEuOTM1LjkzNSAwIDAgMC0uOTM1Ni0uOTM1"
    "NnptLjE2OCAyLjg0NzdWMjRINi40NTVWNC43NDIyem01LjAyMTQgMFYyMC41NDNoMy44NDE4VjQuNzQyMnptNC45NTcg"
    "MFYxNS4yOTFoMy44NDk3VjQuNzQyMnptNC45MzU2IDB2Ni40OTQxaDMuODQxOFY0Ljc0MjJ6Ii8+PC9zdmc+"
)


def get_color(pct: float) -> str:
    """Return shields color name based on coverage percentage."""
    if pct >= 90:
        return "brightgreen"
    elif pct >= 80:
        return "green"
    elif pct >= 70:
        return "yellowgreen"
    elif pct >= 60:
        return "yellow"
    elif pct >= 50:
        return "orange"
    return "red"


def get_color_hex(pct: float) -> str:
    """Return hex color code for fallback SVG."""
    if pct >= 90:
        return "#4c1"
    elif pct >= 80:
        return "#97ca00"
    elif pct >= 70:
        return "#a4a61d"
    elif pct >= 60:
        return "#dfb317"
    elif pct >= 50:
        return "#fe7d37"
    return "#e05d44"


def read_coverage_percent(coverage_json_path: Path) -> float:
    """Extract percentage covered from coverage.json or .coverage file."""
    if coverage_json_path.exists():
        with open(coverage_json_path, encoding="utf-8") as f:
            data = json.load(f)
        return float(data.get("totals", {}).get("percent_covered", 0.0))

    # Fallback to .coverage file
    coverage_db = coverage_json_path.parent / ".coverage"
    if coverage_db.exists():
        try:
            import coverage

            cov = coverage.Coverage(data_file=str(coverage_db))
            cov.load()
            with open(os.devnull, "w", encoding="utf-8") as devnull:
                return float(cov.report(file=devnull))
        except Exception as e:
            print(f"Warning: Failed to read from .coverage: {e}", file=sys.stderr)

    raise FileNotFoundError(f"Could not find coverage data file at {coverage_json_path} or {coverage_db}")


def generate_fallback_svg(pct: int, color_hex: str) -> str:
    """Generate self-contained SVG without external network access."""
    pct_str = f"{pct}%"
    font_fam = "Verdana,Geneva,DejaVu Sans,sans-serif"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="113" height="20" role="img" '
        f'aria-label="coverage: {pct_str}">\n'
        f"  <title>coverage: {pct_str}</title>\n"
        '  <linearGradient id="s" x2="0" y2="100%">\n'
        '    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>\n'
        '    <stop offset="1" stop-opacity=".1"/>\n'
        "  </linearGradient>\n"
        '  <clipPath id="r">\n'
        '    <rect width="113" height="20" rx="3"/>\n'
        "  </clipPath>\n"
        '  <g clip-path="url(#r)">\n'
        '    <rect width="78" height="20" fill="#555"/>\n'
        f'    <rect x="78" width="35" height="20" fill="{color_hex}"/>\n'
        '    <rect width="113" height="20" fill="url(#s)"/>\n'
        "  </g>\n"
        f'  <g fill="#fff" text-anchor="middle" font-family="{font_fam}" '
        'text-rendering="geometricPrecision" font-size="110">\n'
        f'    <image x="5" y="3" width="14" height="14" href="data:image/svg+xml;base64,{PYTEST_ICON_B64}"/>\n'
        '    <g transform="scale(.1)">\n'
        '      <text x="485" y="150" fill="#010101" fill-opacity=".3" textLength="510">coverage</text>\n'
        '      <text x="485" y="140" textLength="510">coverage</text>\n'
        f'      <text x="945" y="150" fill="#010101" fill-opacity=".3" textLength="250">{pct_str}</text>\n'
        f'      <text x="945" y="140" textLength="250">{pct_str}</text>\n'
        "    </g>\n"
        "  </g>\n"
        "</svg>\n"
    )


def generate_badge(coverage_json: Path, output_svg: Path) -> None:
    """Generate SVG badge from coverage data."""
    raw_pct = read_coverage_percent(coverage_json)
    pct = round(raw_pct)
    color = get_color(pct)
    color_hex = get_color_hex(pct)

    url = f"https://img.shields.io/badge/coverage-{pct}%25-{color}?logo=pytest&logoColor=white"
    svg_content: str | None = None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            svg_content = resp.read().decode("utf-8")
    except Exception as exc:
        print(f"Notice: shields.io request failed ({exc}); using fallback SVG generator.")
        svg_content = generate_fallback_svg(pct, color_hex)

    output_svg.write_text(svg_content, encoding="utf-8")
    print(f"Generated coverage badge at {output_svg} ({pct}%, {color})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate coverage SVG badge")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("coverage.json"),
        help="Path to coverage.json file (default: coverage.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("coverage.svg"),
        help="Path to output SVG file (default: coverage.svg)",
    )
    args = parser.parse_args()
    generate_badge(args.input, args.output)


if __name__ == "__main__":
    main()
