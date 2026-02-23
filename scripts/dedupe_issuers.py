#!/usr/bin/env python3
"""
Deduplicate issuer list: normalize names (strip parentheticals like ($100), (was NYCB))
and output a unique sorted list to watchlist_issuers.txt.
Note: The live watchlist is ticker-based (watchlist_preferred_tickers.txt +
watchlist_cef_tickers.txt). This script is for regenerating watchlist_issuers.txt
from a raw issuer-names file if you have one; watchlist_issuers_raw.txt was removed.
"""
import re
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "watchlist_issuers_raw.txt"
OUT = Path(__file__).resolve().parent.parent / "watchlist_issuers.txt"


def normalize_for_key(name: str) -> str:
    """Normalize for dedup: strip parentheticals and extra space, lowercase for comparison."""
    s = (name or "").strip()
    # Remove parenthetical suffixes: ($100), ($50), (was NYCB), (Exantas), (S50), (reset), etc.
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    s = re.sub(r"\s*--[^\-]+$", "", s)  # e.g. "--$20/Issue"
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(".", "")  # B. Riley = B Riley for dedup
    return s.lower()


def canonical_name(name: str) -> str:
    """Prefer the version without parenthetical (shorter)."""
    s = (name or "").strip()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    s = re.sub(r"\s*--[^\-]+$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Title case for consistency (optional)
    return s if s else name.strip()


def main():
    lines = RAW.read_text().strip().splitlines()
    seen_keys = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        key = normalize_for_key(line)
        if not key:
            continue
        # Keep the first (or shortest) canonical name per key
        can = canonical_name(line)
        if key not in seen_keys or len(can) < len(seen_keys[key]):
            seen_keys[key] = can
    unique = sorted(seen_keys.values(), key=lambda x: x.upper())
    OUT.write_text("\n".join(unique) + "\n")
    print(f"Wrote {len(unique)} unique issuers to {OUT}")


if __name__ == "__main__":
    main()
