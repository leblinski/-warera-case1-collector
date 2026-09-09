#!/usr/bin/env python3
"""Ask the game for a player's name, given the id a trade row carries.

Every order and every fill names both sides, but as an opaque id:

    {"user": "6983939d09d4e2cdfdac70b3", "price": 3.582, "quantity": 317}

The game shows PartyBanana and WINSTONTURTLE for the same rows, so the mapping exists.
This finds the procedure that returns it, and answers the two things that decide whether a
ledger can show names at all:

  1. Which procedure, on which base, with which input shape, returns a user - and whether
     the row carries a display name.
  2. Whether names can be fetched in bulk. There are more than eight thousand accounts in
     the cache and a request costs about fifteen seconds, so one call per account is not a
     thing that can ever run. Without a batch shape the ledger can only ever name the few
     accounts that matter, resolved slowly and cached forever.

Ids come from the committed cache, so the probe invents nothing. Read-only, manual, prints
no key.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from collector import GATEWAY, OFFICIAL, Client, CollectionError, ApiError

# Ordered widest-first: a procedure that takes a list is worth more than one that does not,
# because eight thousand single lookups is not a budget any run has.
BATCH = ("user.getUsersLite", "user.getUsers", "user.getByIds")
SINGLE = ("user.getUserLite", "user.getUser", "user.getById", "user.getProfile",
          "user.getPublicProfile")
NAME_KEYS = ("username", "name", "nickname", "displayName", "pseudo")


def ids_from_cache(limit=3):
    """Real ids, taken from what the collector already published."""
    path = os.path.join(ROOT, "data", "warera_case1_market.json")
    payload = json.load(open(path))
    found = []
    for row in (payload.get("commodities") or {}).values():
        for side in ("buy_orders", "sell_orders"):
            for order in ((row.get("order_book") or {}).get(side) or []):
                if isinstance(order.get("user"), str):
                    found.append(order["user"])
    for cat in (payload.get("categories") or {}).values():
        for tx in (cat.get("transactions") or [])[:50]:
            found.extend(x for x in (tx.get("seller_id"), tx.get("buyer_id")) if isinstance(x, str))
    seen = list(dict.fromkeys(found))
    return seen[:limit]


def shapes(user_id, batch):
    """The input encodings a tRPC procedure plausibly wants, cheapest guess first."""
    if batch:
        return (("{userIds:[...]}", {"userIds": [user_id]}),
                ("{ids:[...]}", {"ids": [user_id]}),
                ("[...]", [user_id]))
    return (('"<id>"', user_id), ("{userId}", {"userId": user_id}), ("{id}", {"id": user_id}))


def name_of(value):
    """A display name anywhere in the response, at any of the shapes a tRPC row takes."""
    if isinstance(value, dict):
        for key in NAME_KEYS:
            if isinstance(value.get(key), str) and value[key]:
                return value[key]
        for nested in value.values():
            found = name_of(nested)
            if found:
                return found
    elif isinstance(value, list):
        for item in value[:5]:
            found = name_of(item)
            if found:
                return found
    return None


def attempt(client, proc, label, payload):
    try:
        return client.call(proc, payload, attempts=1), None
    except (CollectionError, ApiError) as exc:
        return None, str(exc)[:100]


def main():
    key = os.environ.get("WARERA_API_KEY", "").strip()
    ids = ids_from_cache()
    if not ids:
        print("no user ids in the cache; run the collector first", file=sys.stderr)
        return 2
    print(f"{len(ids)} ids from the cache, e.g. {ids[0]}\n")

    # The gateway carries a key and may simply not proxy user procedures; the official API is
    # what the game's own client talks to. Both are asked, official first.
    bases = [("official", OFFICIAL, "")]
    if key:
        bases.append(("gateway", GATEWAY, key))
    else:
        print("WARERA_API_KEY is not set: asking the official base only\n")

    wins = []
    for base_name, base_url, base_key in bases:
        # Built here, not up front: a Client's budget starts at construction, and the second
        # base would spend its whole allowance watching the first one work.
        client = Client(base_url, base_key, max_seconds=420)
        for batch, procs in ((True, BATCH), (False, SINGLE)):
            for proc in procs:
                for label, payload in shapes(ids[0], batch):
                    raw, err = attempt(client, proc, label, payload)
                    if err:
                        print(f"  {base_name:8s} {proc:22s} {label:16s} {err}")
                        # A procedure that does not exist will not exist at another shape
                        # either, and every guess costs about fifteen seconds.
                        if "HTTP 404" in err:
                            break
                        continue
                    name = name_of(raw)
                    print(f"  {base_name:8s} {proc:22s} {label:16s} OK"
                          f"{'  name=' + name if name else '  (no name field)'}")
                    print("    " + json.dumps(raw, separators=(",", ":"))[:400])
                    wins.append((base_name, proc, label, batch, bool(name)))
                    break

    print()
    named = [w for w in wins if w[4]]
    if not named:
        print("VERDICT: nothing returned a display name. The ledger stays on ids.")
        return 1
    for base_name, proc, label, batch, _ in named:
        print(f"VERDICT: {base_name} {proc} with {label} returns a name"
              f"{' and takes a list' if batch else ' one at a time'}")
    if not any(w[3] for w in named):
        print("No batch shape answered, so only accounts worth naming can be resolved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
