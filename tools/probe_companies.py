#!/usr/bin/env python3
"""Does the API say who produces each good?

The collector can see demand in detail - every fill, both counterparties, the whole book -
and nothing at all about supply. How many companies make steel, and whether that number is
growing, is the half of a price that order flow cannot show. If the API will answer it,
that is worth collecting; if it will not, it is worth knowing so the question stops coming
back.

tRPC distinguishes the two cases for us. An unknown procedure answers 404 NOT_FOUND; a
known one given the wrong input answers 400 or 500. So a name that fails with anything
other than 404 exists, and is worth a second look with better input.

Read-only, one attempt each, never prints the key.
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import DEFAULT_BASE_URL, GATEWAY, Client, CollectionError, ApiError

# Plain guesses at the shape the rest of the API uses: noun.getThing, sometimes paginated.
CANDIDATES = [
    ("company.getCompanies", {}), ("company.getAll", {}),
    ("company.getPaginatedCompanies", {"limit": 5}),
    ("company.getCompaniesByItem", {"itemCode": "steel"}),
    ("company.getByItemCode", {"itemCode": "steel"}),
    ("company.getCompany", {}), ("company.search", {"itemCode": "steel"}),
    ("company.getUserCompanies", {}), ("company.getMyCompanies", {}),
    ("companies.getAll", {}),
    ("business.getBusinesses", {}),
    ("factory.getFactories", {}),
    ("item.getProducers", {"itemCode": "steel"}),
    ("itemTrading.getProducers", {"itemCode": "steel"}),
    ("itemTrading.getProduction", {}),
    ("stats.getProduction", {}), ("stats.getItemStats", {"itemCode": "steel"}),
    ("country.getCompanies", {}),
    ("market.getProducers", {"itemCode": "steel"}),
    ("production.getByItem", {"itemCode": "steel"}),
]


def shape(value, depth=0):
    """What came back, in one line, without dumping somebody's whole company list."""
    if isinstance(value, dict):
        keys = list(value)[:8]
        return "{" + ", ".join(keys) + ("…" if len(value) > 8 else "") + "}"
    if isinstance(value, list):
        return f"[{len(value)} items]" + (" " + shape(value[0], depth + 1) if value and depth < 1 else "")
    return type(value).__name__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", choices=("official", "gateway"), default="official")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()
    key = os.environ.get("WARERA_API_KEY", "").strip()
    if not key:
        print("WARERA_API_KEY is not set", file=sys.stderr)
        return 2
    base = GATEWAY if args.base == "gateway" else DEFAULT_BASE_URL
    client = Client(base, key, max_seconds=300)

    print(f"Asking the {args.base} base. 404 means no such procedure; anything else means it exists.\n")
    print(f"{'procedure':<34}{'status':>8}{'ms':>7}  what came back")
    alive = []
    for proc, params in CANDIDATES:
        started = time.monotonic()
        try:
            data = client.call(proc, params, attempts=1, timeout=args.timeout)
            ms = int((time.monotonic() - started) * 1000)
            print(f"{proc:<34}{'OK':>8}{ms:>7}  {shape(data)}")
            alive.append((proc, data))
        except (CollectionError, ApiError) as exc:
            ms = int((time.monotonic() - started) * 1000)
            status = getattr(exc, "status", None)
            tag = str(status) if status else "err"
            note = "no such procedure" if status == 404 else str(exc)[:46]
            print(f"{proc:<34}{tag:>8}{ms:>7}  {note}")
            if status and status != 404:
                alive.append((proc, None))

    print()
    if not alive:
        print("Nothing answered and nothing existed. The API does not publish production,\n"
              "at least not under any of these names.")
    else:
        print("Worth a second look, with better input where it only complained:")
        for proc, data in alive:
            print(f"  {proc}" + ("" if data is None else "   (already returns data)"))
        for proc, data in alive:
            if data is not None:
                print(f"\nFirst row of {proc}:")
                row = data[0] if isinstance(data, list) and data else data
                print("  " + json.dumps(row)[:400])
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
