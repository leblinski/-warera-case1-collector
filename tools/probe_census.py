#!/usr/bin/env python3
"""What a company census would cost, and whether it can be made incremental.

company.getCompanies pages ten ids at a time and will not filter, and company.getById
turns one id into what it produces. Counting producers per good is therefore a walk of the
whole list plus a read of every company, which is affordable once and painful every day.

Unless the list is ordered by when a company last changed. The cursor carries a date, so
if that date is updatedAt then a daily walk can stop at the first company older than the
last census and read only what moved - the difference between six thousand reads a day and
a few dozen. If it is createdAt, only new companies are cheap to find and spotting a
company that switched goods means re-reading all of them.

This settles three things: how long the list really is, what it is ordered by, and what
share of companies change on a given day.

Read-only. Never prints the key.
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import DEFAULT_BASE_URL, Client, CollectionError, ApiError, parse_time

LIST, DETAIL = "company.getCompanies", "company.getById"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=3000)
    ap.add_argument("--sample-every", type=int, default=50, help="detail one company per N pages")
    ap.add_argument("--budget", type=int, default=1500)
    args = ap.parse_args()
    key = os.environ.get("WARERA_API_KEY", "").strip()
    if not key:
        print("WARERA_API_KEY is not set", file=sys.stderr); return 2
    client = Client(DEFAULT_BASE_URL, key, max_seconds=args.budget)

    started = time.monotonic()
    cursor, pages, ids, samples = None, 0, 0, []
    ended = "page limit"
    while pages < args.max_pages:
        params = {"cursor": cursor} if cursor else {}
        try:
            data = client.call(LIST, params, attempts=1, timeout=15)
        except (CollectionError, ApiError) as exc:
            ended = f"stopped: {str(exc)[:60]}"; break
        items = (data or {}).get("items") or []
        ids += len(items); pages += 1
        if items and pages % args.sample_every == 1:
            try:
                row = client.call(DETAIL, {"companyId": items[0]}, attempts=1, timeout=15)
                samples.append((pages, row.get("itemCode"), row.get("createdAt"), row.get("updatedAt")))
            except (CollectionError, ApiError):
                pass
        cursor = (data or {}).get("nextCursor")
        if not cursor:
            ended = "end of list"; break
    secs = time.monotonic() - started

    print(f"Walked {pages} pages, {ids} companies, in {secs:.0f}s - {ended}.\n")
    print(f"{'page':>6}{'itemCode':>14}{'createdAt':>26}{'updatedAt':>26}")
    for page, code, created, updated in samples:
        print(f"{page:>6}{str(code):>14}{str(created):>26}{str(updated):>26}")

    def monotonic(key_index, label):
        vals = [s[key_index] for s in samples if s[key_index]]
        if len(vals) < 3:
            return f"  {label}: too few samples"
        times = [parse_time(v) for v in vals]
        down = all(times[i] >= times[i+1] for i in range(len(times)-1))
        up = all(times[i] <= times[i+1] for i in range(len(times)-1))
        return f"  {label}: {'descending' if down else 'ascending' if up else 'NOT ordered'}"

    print("\nIs the list ordered by one of these?")
    print(monotonic(2, "createdAt"))
    print(monotonic(3, "updatedAt"))

    print(f"\nA full census at this rate: {ids} reads for the ids plus one per company,")
    print(f"so about {(pages + ids) * 0.5 / 60:.0f} minutes of calls if every company is read.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
