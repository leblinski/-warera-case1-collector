#!/usr/bin/env python3
"""Seed the equipment history from the archive that has been accumulating since August.

The collector retains a week of transactions, so left alone the valuation would start with
a week and reach sixty days in two months. The archive already holds seventy-eight, every
sale with its roll, and it is committed - so the history can simply be built from it once
and maintained by the collector afterwards.

Idempotent: a day already written identically is left alone. Read-only against the archive.
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import valuation
from collector import SCHEMA_VERSION


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-dir", type=Path, default=ROOT / "data/archive")
    ap.add_argument("--gear-dir", type=Path, default=ROOT / "data/gear")
    ap.add_argument("--days", type=int, default=90)
    args = ap.parse_args()

    files = sorted(args.archive_dir.glob("*.json"))[-args.days:]
    if not files:
        print(f"No archive under {args.archive_dir}", file=sys.stderr)
        return 1
    args.gear_dir.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    for path in files:
        day = path.stem
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            print(f"  {day}: unreadable ({str(exc)[:40]})")
            continue
        items = {}
        for sale in record.get("sales", []):
            code = sale.get("item_code")
            skills = (sale.get("skills") or {})
            qty = sale.get("quantity")
            money = sale.get("money")
            if not code or not skills or not qty or not money:
                continue
            if sale.get("state") is None or sale.get("state") != sale.get("max_state"):
                continue          # the comps window is full-condition only
            seconds = None
            if sale.get("offer_created_at") and sale.get("sold_at"):
                try:
                    from datetime import datetime
                    a = datetime.fromisoformat(sale["offer_created_at"].replace("Z", "+00:00"))
                    b = datetime.fromisoformat(sale["sold_at"].replace("Z", "+00:00"))
                    seconds = max(0, int((b - a).total_seconds()))
                except ValueError:
                    seconds = None
            items.setdefault(code, []).append(
                (valuation.roll_key(skills), money / qty, seconds))
        out = {"schema_version": SCHEMA_VERSION, "date": day, "items": {}}
        for code, sales in sorted(items.items()):
            cells = valuation.aggregate(sales)
            out["items"][code] = {"cells": cells, "level": valuation.day_level(cells)}
        target = args.gear_dir / f"{day}.json"
        if target.exists():
            try:
                if json.loads(target.read_text(encoding="utf-8")) == out:
                    skipped += 1
                    continue
            except (ValueError, OSError):
                pass
        target.write_text(json.dumps(out, separators=(",", ":"), sort_keys=True) + "\n",
                          encoding="utf-8")
        written += 1
        print(f"  {day}: {len(out['items'])} items, {sum(len(v['cells']) for v in out['items'].values())} cells")
    print(f"\n{written} days written, {skipped} already current, into {args.gear_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
