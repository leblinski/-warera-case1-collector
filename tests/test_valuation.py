"""The valuation's arithmetic, on fixtures small enough to check by hand."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import collector as c
import valuation as v

DAY = "2026-11-01"


def day(cells_by_roll):
    """{roll: [prices]} -> a stored day."""
    sales = [(roll, price, 600) for roll, prices in cells_by_roll.items() for price in prices]
    cells = v.aggregate(sales)
    return {"cells": cells, "level": v.day_level(cells)}


def line_history(days=30, slope=2.0, base=100.0, drift=0.0):
    """An item whose price is base + slope*stat, drifting by a factor each day."""
    out = {}
    for i in range(days):
        date = (datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(days=i)).date().isoformat()
        level = (1 + drift) ** i
        out[date] = day({v.roll_key({"dodge": s}): [(base + slope * s) * level]
                         for s in range(50, 61)})
    return out


class RollKeys(unittest.TestCase):
    def test_round_trip(self):
        roll = {"attack": 280, "criticalChance": 47}
        self.assertEqual(v.parse_roll(v.roll_key(roll)), roll)

    def test_order_is_stable(self):
        self.assertEqual(v.roll_key({"criticalChance": 1, "attack": 2}),
                         v.roll_key({"attack": 2, "criticalChance": 1}))


class Aggregate(unittest.TestCase):
    def test_counts_median_and_seconds(self):
        cells = v.aggregate([("a", 10.0, 60), ("a", 20.0, 120), ("a", 30.0, None), ("b", 5.0, None)])
        self.assertEqual(cells["a"][0], 3)
        self.assertEqual(cells["a"][1], 20.0)
        self.assertEqual(cells["a"][2], 90)
        self.assertIsNone(cells["b"][2])

    def test_level_is_the_median_cell_not_the_busiest(self):
        # One roll trading twenty times must not drag the item's level onto itself.
        cells = v.aggregate([("a", 100.0, None)] * 20 + [("b", 200.0, None), ("c", 300.0, None)])
        self.assertEqual(v.day_level(cells), 200.0)

    def test_empty(self):
        self.assertIsNone(v.day_level({}))


class Pricing(unittest.TestCase):
    def test_a_well_traded_roll_keeps_its_own_median(self):
        model = v.build([(DAY, {v.roll_key({"dodge": 55}): [9, 500.0, None]})], k=1.0)
        self.assertEqual(v.price(model, v.roll_key({"dodge": 55})), 500.0)

    def test_a_single_sale_is_pulled_toward_its_neighbours(self):
        cells = {v.roll_key({"dodge": s}): [8, 100.0 + 2 * s, None] for s in range(50, 60)}
        cells[v.roll_key({"dodge": 60})] = [1, 999.0, None]      # one wild sale
        model = v.build([(DAY, cells)], k=1.0)
        got = v.price(model, v.roll_key({"dodge": 60}))
        self.assertLess(got, 999.0)
        self.assertGreater(got, 220.0)        # but not all the way down to the line

    def test_an_unseen_roll_still_gets_a_price(self):
        cells = {v.roll_key({"dodge": s}): [5, 100.0 + 2 * s, None] for s in range(50, 60)}
        model = v.build([(DAY, cells)], k=1.0)
        got = v.price(model, v.roll_key({"dodge": 70}))
        self.assertIsNotNone(got)
        self.assertGreater(got, v.price(model, v.roll_key({"dodge": 59})))

    def test_two_stat_items_are_priced_within_their_crit_bucket(self):
        # Attack is worth ten a point at crit 50 and one a point at crit 41. A model that
        # pooled them would price the middle of both and be wrong at each end.
        cells = {}
        for crit, slope in ((41, 1.0), (50, 10.0)):
            for attack in range(100, 110):
                cells[v.roll_key({"attack": attack, "criticalChance": crit})] = \
                    [6, 100.0 + slope * attack, None]
        model = v.build([(DAY, cells)], k=1.0)
        low = v.price(model, v.roll_key({"attack": 120, "criticalChance": 41}))
        high = v.price(model, v.roll_key({"attack": 120, "criticalChance": 50}))
        self.assertAlmostEqual(low, 220.0, delta=15)
        self.assertAlmostEqual(high, 1300.0, delta=80)


class Fitting(unittest.TestCase):
    def test_a_steady_item_is_priced_almost_exactly(self):
        got = v.value_item(line_history(days=20))
        self.assertIsNotNone(got)
        self.assertLess(got["accuracy"]["avg_pct"], 1.0)
        self.assertEqual(got["priced_rolls"], 11)

    def test_a_drifting_item_prefers_a_short_window(self):
        steady = v.fit(line_history(days=30, drift=0.0))
        drifting = v.fit(line_history(days=30, drift=0.03))
        self.assertIsNotNone(drifting)
        self.assertLessEqual(drifting["window_days"], steady["window_days"])

    def test_the_level_is_todays_not_the_windows(self):
        # Prices triple over the history; the answer must sit near the end, not the middle.
        got = v.value_item(line_history(days=12, drift=0.10))
        priced = got["rolls"][v.roll_key({"dodge": 50})]["price"]
        self.assertGreater(priced, (100 + 2 * 50) * 1.10 ** 9)

    def test_too_little_history_declines_to_guess(self):
        self.assertIsNone(v.fit({DAY: day({v.roll_key({"dodge": 50}): [100.0]})}))


class Plumbing(unittest.TestCase):
    """The collector's side: bucketing by day, and not rewriting a day still running."""

    def payload(self, now):
        cat = {code: {"name": code, "tier": "mythic", "rarity": "mythic", "slot": "boots",
                      "status": "ok", "last_success_at": c.stamp(now), "transaction_count": 0,
                      "rolls": {}, "transactions": []} for code in ("boots6",)}
        for i, hours in enumerate((2, 26, 50)):
            sold = now - timedelta(hours=hours)
            cat["boots6"]["transactions"].append(c.pack_transaction(c.normalize_transaction({
                "_id": f"tx{i}", "transactionType": "itemMarket", "itemCode": "boots6",
                "money": 400 + i, "quantity": 1,
                "createdAt": c.stamp(sold), "offerCreatedAt": c.stamp(sold - timedelta(minutes=5)),
                "item": {"_id": f"e{i}", "code": "boots6", "state": 100, "maxState": 100,
                         "skills": {"dodge": 55}},
            }, "boots6")))
        return {"categories": cat, "generated_at": c.stamp(now)}

    def test_sales_land_on_the_day_they_sold(self):
        now = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        days = c.gear_day_cells(self.payload(now))
        self.assertEqual(sorted(days), ["2026-11-18", "2026-11-19", "2026-11-20"])

    def test_today_is_held_in_memory_not_written(self):
        now = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        payload = self.payload(now)
        with tempfile.TemporaryDirectory() as tmp:
            written = c.write_gear_history(payload, Path(tmp), now)
            on_disk = sorted(p.stem for p in Path(tmp).glob("*.json"))
            self.assertEqual(written, 2)
            self.assertEqual(on_disk, ["2026-11-18", "2026-11-19"])
            history = c.load_gear_history(payload, Path(tmp), now)
            self.assertIn("2026-11-20", history["boots6"])

    def test_old_days_are_pruned_so_the_directory_settles(self):
        now = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for date in ("2026-01-01", "2026-07-22", "2026-07-24", "2026-11-19"):
                (tmp / f"{date}.json").write_text("{}")
            dropped = c.prune_gear_history(tmp, now)       # 120 days back is 2026-07-23
            kept = sorted(q.stem for q in tmp.glob("*.json"))
            self.assertEqual(dropped, 2)
            self.assertEqual(kept, ["2026-07-24", "2026-11-19"])

    def test_the_read_window_fits_inside_what_disk_keeps(self):
        # A window the fit may choose, plus the days the score holds back, must still be on
        # disk - otherwise retention quietly caps the search.
        self.assertLessEqual(max(v.WINDOWS) + v.SCORE_DAYS, c.GEAR_HISTORY_DAYS)
        self.assertLess(c.GEAR_HISTORY_DAYS, c.GEAR_RETAIN_DAYS)

    def test_the_history_is_committed_by_the_workflow(self):
        # The fit reads months of its own sales. A history written only on the runner would
        # be rebuilt from one day and discarded every run, and the model would never learn.
        flow = Path(__file__).resolve().parent.parent / ".github/workflows/collect.yml"
        committed = [line for line in flow.read_text(encoding="utf-8").splitlines()
                     if line.strip().startswith("git add ")]
        self.assertTrue(committed, "no git add step found in collect.yml")
        self.assertTrue(any("data/gear" in line for line in committed), committed)

    def test_writing_twice_changes_nothing(self):
        now = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        payload = self.payload(now)
        with tempfile.TemporaryDirectory() as tmp:
            c.write_gear_history(payload, Path(tmp), now)
            self.assertEqual(c.write_gear_history(payload, Path(tmp), now), 0)


if __name__ == "__main__":
    unittest.main()
