#!/usr/bin/env python3
"""Can the API be made to say how many companies produce each good?

Round one found exactly one live procedure, company.getCompanies, which answers with a
page of bare company ids and a cursor. Ids alone cannot say who makes steel, so two things
decide whether supply is collectable at all: whether the list can be filtered or counted
per item, and whether a single company can be read for what it produces.

If it filters, counting is a page walk per good. If it only pages the whole world, the
cost is the whole world divided by the page size, which is worth knowing before promising
anything.

Read-only, one attempt each, never prints the key.
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import DEFAULT_BASE_URL, Client, CollectionError, ApiError

LIST = "company.getCompanies"
DETAIL_NAMES = ["company.getCompanyLite", "company.getById", "company.getCompanyById",
                "company.get", "company.getOne", "company.getInfo", "company.getDetails"]
DETAIL_KEYS = ["companyId", "id", "company"]


def ask(client, proc, params, timeout):
    started = time.monotonic()
    try:
        return client.call(proc, params, attempts=1, timeout=timeout), None, int((time.monotonic()-started)*1000)
    except (CollectionError, ApiError) as exc:
        return None, exc, int((time.monotonic()-started)*1000)


def brief(v, n=3):
    if isinstance(v, dict):
        return "{" + ", ".join(list(v)[:10]) + ("…" if len(v) > 10 else "") + "}"
    if isinstance(v, list):
        return f"[{len(v)}]"
    return repr(v)[:60]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", default="steel")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--walk-pages", type=int, default=600)
    args = ap.parse_args()
    key = os.environ.get("WARERA_API_KEY", "").strip()
    if not key:
        print("WARERA_API_KEY is not set", file=sys.stderr); return 2
    client = Client(DEFAULT_BASE_URL, key, max_seconds=480)

    print("1. Does the list take a page size, or a filter?\n")
    print(f"{'input':<46}{'items':>7}{'cursor':>8}{'ms':>7}  note")
    shapes = [{}, {"limit": 50}, {"limit": 100},
              {"itemCode": args.item}, {"itemCode": args.item, "limit": 50},
              {"item": args.item}, {"produces": args.item}, {"countryId": None}]
    first_ids = []
    for params in shapes:
        data, err, ms = ask(client, LIST, params, args.timeout)
        label = json.dumps(params)
        if err:
            print(f"{label:<46}{'-':>7}{'-':>8}{ms:>7}  {str(err)[:40]}")
            continue
        items = (data or {}).get("items") or []
        cur = bool((data or {}).get("nextCursor"))
        if not first_ids and items and isinstance(items[0], str):
            first_ids = items[:]
        print(f"{label:<46}{len(items):>7}{str(cur):>8}{ms:>7}  {brief(data)}")

    print("\n2. Can one company be read?\n")
    if not first_ids:
        print("   No ids came back, so nothing to look up.")
    else:
        cid = first_ids[0]
        found = False
        for proc in DETAIL_NAMES:
            for k in DETAIL_KEYS:
                data, err, ms = ask(client, proc, {k: cid}, args.timeout)
                if err and getattr(err, "status", None) == 404 and k == DETAIL_KEYS[0]:
                    print(f"   {proc:<28} no such procedure"); break
                if not err:
                    print(f"   {proc:<28} OK with {{{k}}}  -> {brief(data)}")
                    print("   " + json.dumps(data)[:500])
                    found = True; break
            if found: break
        if not found:
            print("   None of the detail names answered. Ids may only be usable elsewhere.")

    print("\n3. Can the API just count them?\n")
    # The client bundle names two counting procedures. Both refuse an unauthenticated
    # caller with 401, which is the one error a key can fix, so they are worth asking
    # properly: a count per item would turn a four-hour census into one call a good.
    counters = ["company.getActiveCompaniesCount", "company.getCompaniesCount"]
    goods = [args.item, "wood", "paper", "limestone", "concrete", "iron", "lead",
             "lightAmmo", "oil", "petroleum", "grain", "bread", "coca", "cocain",
             "fish", "cookedFish", "livestock", "steak", "ammo", "heavyAmmo"]
    working = []
    for proc in counters:
        for params in ({}, {"itemCode": args.item}, {"item": args.item}):
            data, err, ms = ask(client, proc, params, args.timeout)
            label = f"{proc} {json.dumps(params)}"
            if err:
                print(f"   {label:<62} {str(err)[:40]}")
                continue
            print(f"   {label:<62} -> {json.dumps(data)[:120]}")
            if "itemCode" in params:
                working.append(proc)
    if working:
        proc = working[0]
        print(f"\n   Counting every good with {proc}:\n")
        print(f"   {'good':<14}{'companies':>10}")
        for code in goods:
            data, err, ms = ask(client, proc, {"itemCode": code}, args.timeout)
            if err:
                print(f"   {code:<14}{'-':>10}  {str(err)[:30]}")
            else:
                n = data if isinstance(data, int) else json.dumps(data)[:40]
                print(f"   {code:<14}{str(n):>10}")
    else:
        print("\n   No counter took an item, so supply per good still means walking the list.")

    print("\n4. How big is the whole list?\n")
    seen, cursor, pages = 0, None, 0
    while pages < args.walk_pages:
        params = {"limit": 100}
        if cursor: params["cursor"] = cursor
        data, err, ms = ask(client, LIST, params, args.timeout)
        if err: print(f"   page {pages+1}: {str(err)[:50]}"); break
        items = (data or {}).get("items") or []
        seen += len(items); pages += 1
        cursor = (data or {}).get("nextCursor")
        if not cursor:
            print(f"   {seen} companies in {pages} pages - that is all of them."); break
    else:
        print(f"   {seen} companies in {pages} pages and still going, so the list is at "
              f"least that long at {seen//max(pages,1)} a page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
