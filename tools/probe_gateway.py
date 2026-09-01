#!/usr/bin/env python3
"""Measure how far back one filtered market request reaches.

The browser calculator reads recent equipment sales with a single filtered request,
`transaction.getPaginatedTransactions` with an `itemCode`, and merges them over the
collector's published history. That only works while the newest row the collector has
and the oldest row the request returns overlap. On a busy item they may not: the request
returns a fixed number of rows, and a fixed number of rows covers less time the faster
the item trades.

This answers the two questions that decide it, against the live Gateway rather than by
arithmetic: what page size does the Gateway actually honour, and how many hours does a
page of that size reach back for the busiest categories.

Read-only. Uses the collector's own rate-limited client, and never prints the key.
"""
import argparse, json, os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import GATEWAY, Client, CollectionError, ApiError, page_data, parse_time

DEFAULT_CODES = ("sniper", "boots4", "jet")
DEFAULT_LIMITS = (100, 200, 500)


def probe(client, code, limit):
    started = time.monotonic()
    try:
        rows, _ = page_data(client.call("transaction.getPaginatedTransactions",
                                        {"limit": limit, "itemCode": code}))
    except (CollectionError, ApiError) as exc:
        return {"code": code, "limit": limit, "ok": False, "detail": str(exc)[:90],
                "ms": int((time.monotonic() - started) * 1000)}
    ms = int((time.monotonic() - started) * 1000)
    stamps = sorted(parse_time(r.get("createdAt")) for r in rows if r.get("createdAt"))
    span = (stamps[-1] - stamps[0]).total_seconds() / 3600 if len(stamps) > 1 else 0.0
    behind = (datetime.now(timezone.utc) - stamps[0]).total_seconds() / 3600 if stamps else 0.0
    return {"code": code, "limit": limit, "ok": True, "rows": len(rows), "ms": ms,
            "span_hours": round(span, 2), "reaches_back_hours": round(behind, 2),
            "wrong_item": sum(1 for r in rows if r.get("itemCode") not in (None, code))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default=",".join(DEFAULT_CODES))
    ap.add_argument("--limits", default=",".join(str(n) for n in DEFAULT_LIMITS))
    args = ap.parse_args()

    key = os.environ.get("WARERA_API_KEY", "").strip()
    if not key:
        print("WARERA_API_KEY is not set", file=sys.stderr)
        return 2
    client = Client(GATEWAY, key, max_seconds=180)

    results = []
    print(f"{'item':<10}{'asked':>7}{'rows':>7}{'ms':>8}{'span h':>9}{'reaches back h':>16}  note")
    for code in [c.strip() for c in args.codes.split(",") if c.strip()]:
        for limit in [int(n) for n in args.limits.split(",")]:
            r = probe(client, code, limit)
            results.append(r)
            if not r["ok"]:
                print(f"{code:<10}{limit:>7}{'-':>7}{r['ms']:>8}{'-':>9}{'-':>16}  REJECTED: {r['detail']}")
                continue
            note = "capped" if r["rows"] < limit else ""
            if r["wrong_item"]:
                note = (note + " " if note else "") + f"{r['wrong_item']} rows of another item"
            print(f"{code:<10}{limit:>7}{r['rows']:>7}{r['ms']:>8}"
                  f"{r['span_hours']:>9}{r['reaches_back_hours']:>16}  {note}")

    honoured = [r for r in results if r["ok"] and r["rows"] >= r["limit"]]
    best = max((r["limit"] for r in honoured), default=None)
    print()
    if best is None:
        print("No page size returned a full page; the Gateway is returning fewer rows than asked.")
    else:
        print(f"Largest page size actually filled: {best}")
    worst = min((r["reaches_back_hours"] for r in results if r.get("ok") and r["rows"]), default=None)
    if worst is not None:
        print(f"Shallowest reach across the items probed: {worst:.2f}h "
              f"- the collector must publish more often than this for the two to meet.")
    print("\nRaw:", json.dumps(results, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
