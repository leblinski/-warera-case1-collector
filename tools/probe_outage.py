#!/usr/bin/env python3
"""Find out whether the sale history can be read at all, and from where.

Since 2026-10-16 16:00 every collector run has come back with nothing new, because
`transaction.getPaginatedTransactions` - the one procedure behind both the equipment
scan and the commodity fills - sits for twelve seconds on the Gateway and then answers
HTTP 500. The order books, on the same base and the same key, are fine.

That leaves three repairs worth trying before deciding to wait, and this asks all three
in one go: does a different request shape get through (maybe one filter path is broken
rather than the procedure), does a smaller page get through (maybe it is a backend
timeout on the query), and does the official API answer where the Gateway does not.

Read-only, one attempt per call so a dead shape costs one timeout rather than four, and
it never prints the key.
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import GATEWAY, OFFICIAL, Client, CollectionError, ApiError, page_data

PROCEDURE = "transaction.getPaginatedTransactions"

# Named so the table says which hypothesis each row kills.
SHAPES = (
    ("bare, 5", {"limit": 5}),
    ("itemMarket, 5", {"limit": 5, "transactionType": "itemMarket"}),
    ("commodityMarket, 5", {"limit": 5, "transactionType": "commodityMarket", "itemCode": "scraps"}),
    ("itemCode only, 5", {"limit": 5, "itemCode": "sniper"}),
    ("what the collector asks", {"limit": 100, "transactionType": "itemMarket"}),
)


def ask(client, params, timeout):
    started = time.monotonic()
    try:
        rows, cursor = page_data(client.call(PROCEDURE, params, attempts=1, timeout=timeout))
    except (CollectionError, ApiError) as exc:
        status = getattr(exc, "status", None)
        return {"ok": False, "status": status, "detail": str(exc)[:70],
                "ms": int((time.monotonic() - started) * 1000)}
    return {"ok": True, "rows": len(rows), "cursor": bool(cursor),
            "ms": int((time.monotonic() - started) * 1000)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    key = os.environ.get("WARERA_API_KEY", "").strip()
    bases = [("gateway", GATEWAY, key)] if key else []
    bases.append(("official", OFFICIAL, key))
    bases.append(("official, no key", OFFICIAL, ""))
    if not key:
        print("WARERA_API_KEY is not set: the Gateway cannot be asked, only the official base.\n")

    results = []
    print(f"{'base':<18}{'shape':<26}{'rows':>6}{'ms':>8}  note")
    for base_name, base_url, base_key in bases:
        client = Client(base_url, base_key or None, max_seconds=240)
        for shape_name, params in SHAPES:
            r = ask(client, params, args.timeout)
            results.append({"base": base_name, "shape": shape_name, **r})
            if r["ok"]:
                note = "answered" + ("" if r["cursor"] else ", no cursor")
                print(f"{base_name:<18}{shape_name:<26}{r['rows']:>6}{r['ms']:>8}  {note}")
            else:
                print(f"{base_name:<18}{shape_name:<26}{'-':>6}{r['ms']:>8}  {r['detail']}")

    working = [r for r in results if r["ok"] and r.get("rows")]
    print()
    if not working:
        print("Nothing answered. The sale history is unreadable from either base, in any shape,"
              "\nso there is nothing to repair on our side: it has to come back upstream.")
    else:
        for base_name in dict.fromkeys(r["base"] for r in working):
            shapes = [r["shape"] for r in working if r["base"] == base_name]
            print(f"{base_name} answered for: {', '.join(shapes)}")
        print("\nThe collector can be pointed at whichever base and shape above returned rows.")
    print("\nRaw:", json.dumps(results, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
