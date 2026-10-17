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
    ("itemCode only, 5", {"limit": 5, "itemCode": "sniper"}),
    ("equipment, as collected", {"limit": 100, "transactionType": "itemMarket"}),
    ("goods, as collected", {"limit": 25, "transactionType": "trading", "itemCode": "scraps"}),
)


# The Gateway answers 500 where a 400 belongs - user.getUserLite given a bare string
# does it - so a 500 alone cannot tell a broken backend from a rejected input shape.
# What tells them apart is how long it takes, and these calibrate that: a healthy
# procedure asked correctly, and the same one asked wrongly on purpose.
CONTROLS = (
    ("getTopOrders, correct input", "tradingOrder.getTopOrders", {"itemCode": "scraps", "limit": 5}),
    ("getTopOrders, wrong input", "tradingOrder.getTopOrders", "not-an-object"),
)


def ask(client, params, timeout, procedure=PROCEDURE):
    started = time.monotonic()
    try:
        payload = client.call(procedure, params, attempts=1, timeout=timeout)
        if procedure == PROCEDURE:
            rows, cursor = page_data(payload)
        else:
            # A book, not a page: count one side of it so the row says something.
            rows, cursor = (payload or {}).get("sellOrders") or [], None
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
    if key:
        control_client = Client(GATEWAY, key, max_seconds=120)
        for name, procedure, params in CONTROLS:
            r = ask(control_client, params, args.timeout, procedure)
            results.append({"base": "gateway", "shape": name, **r})
            note = "answered" if r["ok"] else r["detail"]
            print(f"{'gateway':<18}{name:<26}{(r.get('rows') if r['ok'] else '-'):>6}{r['ms']:>8}  {note}")
        print()
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

    rejection_ms = [r["ms"] for r in results
                    if r["shape"] == "getTopOrders, wrong input" and not r["ok"]]
    shape_names = {name for name, _ in SHAPES}
    history_ms = [r["ms"] for r in results
                  if r["base"] == "gateway" and r["shape"] in shape_names and not r["ok"]]
    if rejection_ms and history_ms:
        print(f"The Gateway rejects a bad input in {min(rejection_ms)} ms and fails the sale "
              f"history in {min(history_ms)} ms.\nA gap that wide is a backend giving up, "
              "not an input it dislikes.\n")

    working = [r for r in results if r["ok"] and r.get("rows")]
    print()
    if not working and all(r.get("status") == 503 for r in results if not r["ok"]):
        print("Every call failed before it was answered, so this probe reached nothing and"
              "\nproves nothing. Run it somewhere the two hosts are reachable.")
    elif not working:
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
