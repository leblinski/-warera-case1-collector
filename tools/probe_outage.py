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
from collector import (GATEWAY, OFFICIAL, Client, CollectionError, ApiError, page_data,
                       ROOT, number, parse_time)

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

# Changing base is only safe if the new base serves everything the collector asks for,
# not just the procedure that broke. These are the other three, so a switch cannot fix
# the sale history by breaking the books.
WHOLE_SURFACE = (
    ("getTopOrders", "tradingOrder.getTopOrders", {"itemCode": "scraps", "limit": 5}),
    ("getPrices", "itemTrading.getPrices", None),
    ("getUserLite", "user.getUserLite", {"userId": "6a15ea8a40616a7ecb782238"}),
)


def ask(client, params, timeout, procedure=PROCEDURE):
    started = time.monotonic()
    try:
        payload = client.call(procedure, params, attempts=1, timeout=timeout)
        if procedure == PROCEDURE:
            rows, cursor = page_data(payload)
        elif isinstance(payload, dict) and "sellOrders" in payload:
            # A book, not a page: count one side of it so the row says something.
            rows, cursor = payload.get("sellOrders") or [], None
        else:
            # A price table or a single user: report how many fields came back.
            rows, cursor = payload if hasattr(payload, "__len__") else [payload], None
    except (CollectionError, ApiError) as exc:
        status = getattr(exc, "status", None)
        return {"ok": False, "status": status, "detail": str(exc)[:70],
                "ms": int((time.monotonic() - started) * 1000)}
    return {"ok": True, "rows": len(rows), "cursor": bool(cursor),
            "ms": int((time.monotonic() - started) * 1000)}


def archived_sales(codes):
    """Every archived sale for these codes, by transaction id.

    The archive was built entirely through the Gateway. If the official base hands back
    the same ids for the same sales, the two are the same records and the collector can
    change base without double-counting a single fill. If it re-ids them, it cannot.
    """
    held = {}
    for path in sorted((ROOT / "data/archive").glob("20??-??-??.json")):
        day = json.loads(path.read_text(encoding="utf-8"))
        for sale in day.get("sales", []):
            if sale.get("item_code") in codes:
                held[sale.get("id")] = sale
    return held


def check_identity(client, codes, timeout, max_pages=12):
    """Page one item back until it crosses what the archive already holds, then compare.

    A single page of a busy item covers only a few hours, and the archive stops nearly a
    day back, so one page proves nothing either way. This keeps asking for the next page
    until the rows are older than the newest sale already archived for that item, which is
    the only point where the two sets can be compared at all.
    """
    held = archived_sales(set(codes))
    print(f"Archived sales for {', '.join(codes)}: {len(held)}, all collected through the Gateway.")
    if not held:
        print("Nothing archived for these codes, so identity cannot be checked here.")
        return
    for code in codes:
        mine = {i: s for i, s in held.items() if s.get("item_code") == code}
        if not mine:
            print(f"  {code:<10} nothing archived")
            continue
        newest = max(parse_time(s["sold_at"]) for s in mine.values())
        cursor, pages, rows, oldest = None, 0, [], None
        while pages < max_pages:
            params = {"itemCode": code, "limit": 100}
            if cursor:
                params["cursor"] = cursor
            try:
                page, cursor = page_data(client.call(PROCEDURE, params, attempts=1, timeout=timeout))
            except (CollectionError, ApiError) as exc:
                print(f"  {code:<10} could not be read: {str(exc)[:60]}")
                break
            pages += 1
            rows.extend(page)
            stamps = [parse_time(r["createdAt"]) for r in page if r.get("createdAt")]
            oldest = min(stamps) if stamps else oldest
            if not cursor or (oldest and oldest < newest):
                break
        if not rows:
            continue
        ids = {r.get("_id") or r.get("id") for r in rows if isinstance(r, dict)}
        overlap = [r for r in rows if (r.get("_id") or r.get("id")) in mine]
        reached = f"{oldest:%m-%d %H:%M}" if oldest else "?"
        print(f"  {code:<10} {pages} pages, {len(ids)} rows, back to {reached}, "
              f"archive ends {newest:%m-%d %H:%M}, {len(overlap)} ids in both")
        if oldest is None or oldest >= newest:
            print(f"             did not reach the archive in {max_pages} pages: inconclusive")
            continue
        if not overlap:
            print("             NO shared ids where the two sets overlap: the bases "
                  "re-id sales, so the collector cannot simply change base")
            continue
        row = overlap[0]
        txid = row.get("_id") or row.get("id")
        archived = mine[txid]
        pairs = [("money", archived.get("money"), number(row.get("money"))),
                 ("quantity", archived.get("quantity"), number(row.get("quantity"))),
                 ("sold_at", archived.get("sold_at"), row.get("createdAt"))]
        verdict = "identical" if all(a == b for _, a, b in pairs) else "SAME ID, DIFFERENT SALE"
        print(f"             {txid[:10]}: " +
              ", ".join(f"{k} {a!r} vs {b!r}" for k, a, b in pairs) + f" - {verdict}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--identity-codes", default="jet,tank")
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
    official_works = any(r["ok"] and r.get("rows") and r["base"] == "official" for r in results)
    if official_works:
        print("Does the official base serve the rest of what the collector asks for?")
        surface = Client(OFFICIAL, key, max_seconds=120)
        for name, procedure, params in WHOLE_SURFACE:
            r = ask(surface, params, args.timeout, procedure)
            got = f"{r['rows']} back" if r["ok"] else r["detail"]
            print(f"  {name:<14}{r['ms']:>7} ms  {got}")
        print()

        print("Do the two bases agree on what a sale is?")
        codes = [c.strip() for c in args.identity_codes.split(",") if c.strip()]
        check_identity(Client(OFFICIAL, key, max_seconds=120), codes, args.timeout)

    print("Raw:", json.dumps(results, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
