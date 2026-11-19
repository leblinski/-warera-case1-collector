#!/usr/bin/env python3
"""What is everyone building right now?

A full census is out of reach and always was: company.getCompanies takes no filter - not
itemCode, not item, not produces - answers ten bare ids a page whatever limit you ask for,
and both counting procedures refuse our key outright. Thirty thousand companies at ten a
page, each needing its own read to say what it makes, is four hours of calls for a number
that changes daily.

A sample is better than that, and not only because it is cheaper. The list comes back
newest-and-most-recently-moved first: the first page of an unfiltered call held a company
created half an hour earlier. So the front of the list is not a random slice of the world,
it is what people are doing this week - which is the half of supply that today's price has
not priced in yet. A thousand of those says what is being built now, and that is a leading
number where a total would only repeat what the market already knows.

Read-only. Never prints the key.
"""
import argparse, collections, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import DEFAULT_BASE_URL, Client, CollectionError, ApiError

LIST = "company.getCompanies"
DETAIL = "company.getById"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=100, help="pages of ten ids to sample")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()
    key = os.environ.get("WARERA_API_KEY", "").strip()
    if not key:
        print("WARERA_API_KEY is not set", file=sys.stderr)
        return 2
    client = Client(DEFAULT_BASE_URL, key, max_seconds=510)

    ids, cursor, pages = [], None, 0
    started = time.monotonic()
    while pages < args.pages:
        params = {"cursor": cursor} if cursor else {}
        try:
            data = client.call(LIST, params, attempts=1, timeout=args.timeout)
        except (CollectionError, ApiError) as exc:
            print(f"list stopped after {pages} pages: {str(exc)[:60]}")
            break
        ids.extend(data.get("items") or [])
        cursor = data.get("nextCursor")
        pages += 1
        if not cursor:
            break
    print(f"{len(ids)} companies sampled from the front of the list "
          f"in {pages} pages, {time.monotonic()-started:.0f}s\n")

    goods = collections.Counter()
    engines = collections.Counter()
    regions = collections.Counter()
    read, failed = 0, 0
    for cid in ids:
        try:
            co = client.call(DETAIL, {"companyId": cid}, attempts=1, timeout=args.timeout)
        except (CollectionError, ApiError):
            failed += 1
            continue
        read += 1
        goods[co.get("itemCode") or "?"] += 1
        engines[(co.get("activeUpgradeLevels") or {}).get("automatedEngine") or 1] += 1
        regions[co.get("region") or "?"] += 1

    print(f"read {read}, unreadable {failed}, in {time.monotonic()-started:.0f}s total\n")
    if not read:
        return 0
    print(f"{'good':<14}{'companies':>10}{'share':>8}")
    for code, n in goods.most_common():
        print(f"{code:<14}{n:>10}{n/read*100:>7.1f}%")
    print(f"\n{'engine':<14}{'companies':>10}{'share':>8}")
    for lv, n in sorted(engines.items()):
        print(f"{lv:<14}{n:>10}{n/read*100:>7.1f}%")
    print(f"\n{len(regions)} distinct regions; the busiest:")
    for rid, n in regions.most_common(6):
        print(f"   {rid}  {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
