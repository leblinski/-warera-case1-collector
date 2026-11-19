#!/usr/bin/env python3
"""Does the API say what a country holds in stock?

Production tells you what is being made; stock tells you what is sitting there waiting to
be sold, which is the other half of a supply picture and the half that moves a price
fastest. A country sitting on a mountain of paper is a different market from one that has
none, at the same production rate and the same book.

country.getAllCountries is already known to answer. So two questions: does a country
object already carry its holdings, and if not, is there a procedure that will say.

Read-only. Never prints the key.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import DEFAULT_BASE_URL, Client, CollectionError, ApiError

STOCKISH = re.compile(r"stock|storage|invent|resource|warehouse|item|good|supply|reserve", re.I)
NAMES = ["country.getStock", "country.getStorage", "country.getInventory",
         "country.getResources", "country.getWarehouse", "country.getItems",
         "country.getById", "country.getCountry", "government.getStock",
         "stock.getByCountry", "storage.getByCountry", "country.getStockpile"]
KEYS = ["countryId", "id", "country"]


def walk(value, path="", out=None, depth=0):
    """Field names anywhere in the object that sound like holdings."""
    out = [] if out is None else out
    if depth > 4:
        return out
    if isinstance(value, dict):
        for k, v in value.items():
            here = f"{path}.{k}" if path else k
            if STOCKISH.search(k):
                out.append((here, type(v).__name__,
                            (list(v)[:6] if isinstance(v, dict) else
                             (f"[{len(v)}]" if isinstance(v, list) else repr(v)[:40]))))
            walk(v, here, out, depth + 1)
    elif isinstance(value, list) and value:
        walk(value[0], path + "[0]", out, depth + 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--good", default="paper")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()
    key = os.environ.get("WARERA_API_KEY", "").strip()
    if not key:
        print("WARERA_API_KEY is not set", file=sys.stderr); return 2
    client = Client(DEFAULT_BASE_URL, key, max_seconds=300)

    print("1. What does a country object already carry?\n")
    try:
        countries = client.call("country.getAllCountries", {}, attempts=1, timeout=args.timeout)
    except (CollectionError, ApiError) as exc:
        print("   country.getAllCountries:", str(exc)[:70]); return 1
    rows = countries if isinstance(countries, list) else (countries or {}).get("items") or []
    print(f"   {len(rows)} countries")
    if not rows:
        return 1
    one = rows[0]
    print(f"   top-level fields: {', '.join(list(one)[:24])}")
    hits = walk(one)
    if hits:
        print("\n   fields that sound like holdings:")
        for path, kind, sample in hits:
            print(f"     {path:<36}{kind:<8}{sample}")
    else:
        print("\n   nothing in the country object looks like a stockpile.")

    cid = one.get("_id") or one.get("id")
    name = one.get("name") or cid
    print(f"\n2. Is there a procedure that will say? (asking about {name})\n")
    for proc in NAMES:
        shown = False
        for k in KEYS:
            try:
                data = client.call(proc, {k: cid}, attempts=1, timeout=args.timeout)
            except (CollectionError, ApiError) as exc:
                if getattr(exc, "status", None) == 404:
                    print(f"   {proc:<28} no such procedure"); shown = True; break
                continue
            print(f"   {proc:<28} OK with {{{k}}}")
            print("     " + json.dumps(data)[:420])
            for path, kind, sample in walk(data):
                print(f"       {path:<34}{kind:<8}{sample}")
            shown = True; break
        if not shown:
            print(f"   {proc:<28} exists but refused every input shape tried")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
