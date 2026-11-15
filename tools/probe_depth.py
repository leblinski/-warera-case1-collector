#!/usr/bin/env python3
"""How deep an order book the Gateway will actually hand over, and what is in it.

Two questions the published data cannot answer. First, depth: the collector asks for 100
orders a side, and a good like bread comes back with 83 distinct ask prices, which is
close enough to the cap to suspect the book is being cut off rather than exhausted. If a
larger limit is honoured there is more ladder to show. Second, shape: six goods have never
once produced a book, because one order with a price or quantity the collector rejects
throws away the whole side. This prints the offending rows instead of discarding them.

Read-only. Never prints the key.
"""
import argparse, json, os, sys, time, collections

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import DEFAULT_BASE_URL, Client, CollectionError, ApiError, number

PROCEDURE = "tradingOrder.getTopOrders"
# Goods that always have a book, goods that never do, and goods that come and go.
DEFAULT_CODES = "bread,cookedFish,scraps,grain,limestone,ammo,woodenCase,coca"
DEFAULT_LIMITS = "100,200,500,1000"


def sides(payload):
    if not isinstance(payload, dict):
        return None
    return (payload.get("buyOrders") or [], payload.get("sellOrders") or [])


def rungs(orders):
    levels = collections.defaultdict(float)
    bad = []
    for o in orders:
        if not isinstance(o, dict):
            bad.append(o); continue
        p, q = number(o.get("price")), number(o.get("quantity"))
        if p is None or q is None or p <= 0 or q < 0:
            bad.append(o); continue
        levels[round(p, 3)] += q
    return levels, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default=DEFAULT_CODES)
    ap.add_argument("--limits", default=DEFAULT_LIMITS)
    args = ap.parse_args()
    key = os.environ.get("WARERA_API_KEY", "").strip()
    if not key:
        print("WARERA_API_KEY is not set", file=sys.stderr)
        return 2
    client = Client(DEFAULT_BASE_URL, key, max_seconds=300)

    print(f"{'good':<12}{'asked':>7}{'buys':>7}{'sells':>7}{'b rungs':>9}{'a rungs':>9}"
          f"{'bad':>5}{'ms':>7}  note")
    offenders = []
    for code in [c.strip() for c in args.codes.split(",") if c.strip()]:
        for limit in [int(n) for n in args.limits.split(",")]:
            started = time.monotonic()
            try:
                payload = client.call(PROCEDURE, {"itemCode": code, "limit": limit}, attempts=1)
            except (CollectionError, ApiError) as exc:
                print(f"{code:<12}{limit:>7}{'-':>7}{'-':>7}{'-':>9}{'-':>9}{'-':>5}"
                      f"{int((time.monotonic()-started)*1000):>7}  {str(exc)[:40]}")
                continue
            ms = int((time.monotonic() - started) * 1000)
            got = sides(payload)
            if got is None:
                print(f"{code:<12}{limit:>7}  unrecognised payload: {str(payload)[:40]}")
                continue
            buys, sells = got
            bl, bbad = rungs(buys)
            al, abad = rungs(sells)
            bad = bbad + abad
            offenders.extend((code, o) for o in bad[:2])
            # A side shorter than asked has been exhausted; a side at the cap was cut off.
            capped = [s for s, rows in (("buy", buys), ("sell", sells)) if len(rows) >= limit]
            note = ("CAPPED: " + ",".join(capped)) if capped else "exhausted, this is the whole book"
            print(f"{code:<12}{limit:>7}{len(buys):>7}{len(sells):>7}{len(bl):>9}{len(al):>9}"
                  f"{len(bad):>5}{ms:>7}  {note}")

    if offenders:
        print("\nOrders the collector currently throws whole books away for:")
        for code, o in offenders[:12]:
            print(f"  {code:<12}{json.dumps(o)[:150]}")
    else:
        print("\nNo order was rejected by the collector's own validation in this sample.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
