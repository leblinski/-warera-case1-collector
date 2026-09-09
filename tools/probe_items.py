#!/usr/bin/env python3
"""Ask the game which items trade, and whether their trades are readable.

The collector tracks 36 equipment categories by name and exactly three commodities -
case1, scraps, steel - written into a dict by hand. Unikhorne's board shows more than
twenty, so the hand-written list is short, and a hand-written list copied off someone
else's screenshot would be short again the next time the game adds an item.

itemTrading.getPrices is already called unfiltered on every run and all but three of its
rows are thrown away. This reports what is in it, so the list can be derived rather than
typed, and answers the two things that decide whether commodities can be charted properly:

  1. Every code getPrices returns, which of them are the known equipment, and what a row
     looks like - specifically whether it carries a display name.
  2. Whether a commodity has an order book and a readable trade history. Without
     transaction.getPaginatedTransactions per commodity there is no volume and no trade
     prints, and candles could only ever be built from the book touch.

Read-only, manual, prints no key.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import GATEWAY, Client, CollectionError, ApiError, normalize_prices, page_data

EQUIPMENT = set()
try:
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "case1_items.json")))
    EQUIPMENT = {row["item_code"] for row in cfg}
except Exception as exc:  # pragma: no cover - the probe should still run
    print("could not read config/case1_items.json:", exc)

KNOWN = {"case1", "scraps", "steel"}


def try_call(client, proc, payload=None):
    try:
        return client.call(proc, payload or {}), None
    except (CollectionError, ApiError) as exc:
        return None, str(exc)[:110]


def main():
    key = os.environ.get("WARERA_API_KEY", "").strip()
    if not key:
        print("WARERA_API_KEY is not set", file=sys.stderr)
        return 2
    client = Client(GATEWAY, key, max_seconds=240)

    raw, err = try_call(client, "itemTrading.getPrices")
    if err:
        print("itemTrading.getPrices: REJECTED:", err)
        return 1
    prices = normalize_prices(raw)
    print(f"itemTrading.getPrices: {len(prices)} codes\n")
    sample = next(iter(prices.values()))
    print("one row:", json.dumps(sample, separators=(",", ":"))[:300], "\n")

    others = sorted(c for c in prices if c not in EQUIPMENT)
    equip = sorted(c for c in prices if c in EQUIPMENT)
    print(f"{len(equip)} of the {len(EQUIPMENT)} known equipment codes appear here")
    missing = sorted(EQUIPMENT - set(prices))
    if missing:
        print("  equipment absent from getPrices:", ", ".join(missing))
    print(f"\n{len(others)} non-equipment codes (the tradeable items tab):")
    for c in others:
        row = prices[c]
        price = row.get("price") if isinstance(row, dict) else row
        name = row.get("name") or row.get("displayName") if isinstance(row, dict) else None
        mark = "  <-- already collected" if c in KNOWN else ""
        print(f"  {c:<22}{str(price)[:12]:>14}   {name or '(no name field)'}{mark}")

    # Do the new ones actually have a book, and are their trades readable?
    print("\nBook and trade history for a sample of the new codes:")
    for c in [x for x in others if x not in KNOWN][:5] + sorted(KNOWN):
        book, berr = try_call(client, "tradingOrder.getTopOrders", {"itemCode": c, "limit": 100})
        if berr:
            bnote = f"book REJECTED: {berr}"
        else:
            buys = (book or {}).get("buyOrders") or []
            sells = (book or {}).get("sellOrders") or []
            bnote = f"book ok ({len(buys)} buy / {len(sells)} sell orders)"
        tx, terr = try_call(client, "transaction.getPaginatedTransactions", {"limit": 20, "itemCode": c})
        if terr:
            tnote = f"trades REJECTED: {terr}"
        else:
            rows, _ = page_data(tx)
            tnote = f"trades ok ({len(rows)} rows)"
            if rows:
                tnote += " keys " + str(sorted(rows[0])[:10])
        print(f"  {c:<22}{bnote:<44}{tnote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
