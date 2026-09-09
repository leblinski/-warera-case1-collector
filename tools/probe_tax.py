#!/usr/bin/env python3
"""Ask the game what a country's taxes are, so the calculator can stop asking the reader.

The calculator carries two tax fields, "Yours" and "Rivals", and defaults both to 1%.
Only one of them is really the reader's to know: yours sets what the marketplace displays
for a price you type, and rivals is an assumption about the sellers whose completed sales
the history is built from. Both are guesses today.

This answers whether they need to be. It is read-only, manual, and prints no key.

Three things are wanted:
  1. Does a country object carry a market/trade tax at all, and under what name?
  2. What is the spread of that tax across countries - is "the world is at 1%" true?
  3. Can a country be resolved for the reader, so "Yours" could fill itself in?
"""
import json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import GATEWAY, Client, CollectionError, ApiError

TAXISH = re.compile(r"tax|fee|vat|duty|tariff|rate", re.I)


def walk(node, path=""):
    """Every leaf in a nested object, as a flat path -> value list."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, path + "." + k if path else k)
    elif isinstance(node, list):
        if node:
            yield from walk(node[0], path + "[]")
    else:
        yield path, node


def try_call(client, proc, payload=None):
    try:
        return client.call(proc, payload or {}), None
    except (CollectionError, ApiError) as exc:
        return None, str(exc)[:120]


def main():
    key = os.environ.get("WARERA_API_KEY", "").strip()
    if not key:
        print("WARERA_API_KEY is not set", file=sys.stderr)
        return 2
    client = Client(GATEWAY, key, max_seconds=180)

    data, err = try_call(client, "country.getAllCountries")
    if err:
        print("country.getAllCountries: REJECTED:", err)
        return 1

    rows = data if isinstance(data, list) else (data or {}).get("countries") or []
    if isinstance(data, dict) and not rows:
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                rows = v
                break
    print(f"country.getAllCountries: {len(rows)} countries\n")
    if not rows:
        print("Raw shape:", json.dumps(data, separators=(",", ":"))[:600])
        return 1

    leaves = list(walk(rows[0]))
    print("Fields on one country:")
    for p, v in leaves:
        mark = "  <-- tax-ish" if TAXISH.search(p) else ""
        print(f"  {p:<44}{json.dumps(v)[:40]}{mark}")

    taxfields = [p for p, _ in leaves if TAXISH.search(p)]
    if not taxfields:
        print("\nNo tax-shaped field on a country. Nothing to read; the fields stay manual.")
    for f in taxfields:
        vals = []
        for r in rows:
            cur = r
            for part in f.split("."):
                cur = (cur or {}).get(part) if isinstance(cur, dict) else None
            if isinstance(cur, (int, float)):
                vals.append(cur)
        if not vals:
            continue
        vals.sort()
        c = Counter(vals)
        mid = vals[len(vals) // 2]
        print(f"\n{f}: {len(vals)} countries, min {vals[0]}, median {mid}, max {vals[-1]}")
        print("  most common:", ", ".join(f"{v}x{n}" for v, n in c.most_common(6)))

    # Can a reader's own country be resolved? The calculator already reads a profile.
    for proc in ("user.getMe", "user.getUserLite", "country.getCountryById"):
        payload = {"countryId": rows[0].get("_id") or rows[0].get("id")} if "ById" in proc else {}
        got, e = try_call(client, proc, payload)
        print(f"\n{proc}: {'REJECTED: ' + e if e else 'ok, keys ' + str(list(got)[:12] if isinstance(got, dict) else type(got).__name__)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
